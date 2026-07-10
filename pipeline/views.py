import csv
from django.db.models import Prefetch, Sum, Count, Q, Case, When, DecimalField
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics, serializers

from pipeline.models import PipelineStage, PipelineLead, ActivityLog
from pipeline.serializers import PipelineStageSerializer, PipelineLeadSerializer

class BoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stages = PipelineStage.objects.filter(user=request.user).prefetch_related(
            Prefetch('leads', queryset=PipelineLead.objects.order_by('order').select_related('lead'))
        ).order_by('order')
        
        serializer = PipelineStageSerializer(stages, many=True)
        return Response(serializer.data)

class StatsView(APIView):
    """Optimized: single query with conditional aggregation instead of 4 separate queries."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = PipelineLead.objects.filter(user=request.user).aggregate(
            total_value=Sum('deal_value'),
            won_value=Sum(
                Case(
                    When(stage__system_key='closed_won', then='deal_value'),
                    default=0,
                    output_field=DecimalField(),
                )
            ),
            total_leads=Count('id'),
            won_leads=Count(
                Case(When(stage__system_key='closed_won', then='id'))
            ),
        )

        total_value = stats['total_value'] or 0.00
        won_value = stats['won_value'] or 0.00
        total_leads = stats['total_leads']
        won_leads = stats['won_leads']
        conversion_rate = round((won_leads / total_leads * 100), 2) if total_leads > 0 else 0.0

        return Response({
            "total_deal_value": total_value,
            "won_deal_value": won_value,
            "total_leads": total_leads,
            "conversion_rate": conversion_rate,
        })

class PipelineLeadListCreateView(generics.ListCreateAPIView):
    serializer_class = PipelineLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PipelineLead.objects.filter(
            user=self.request.user
        ).select_related('lead', 'stage').prefetch_related('logs')

    def perform_create(self, serializer):
        stage = serializer.validated_data['stage']
        if stage.user != self.request.user:
            raise serializers.ValidationError("Invalid stage.")
        
        last_order = PipelineLead.objects.filter(stage=stage).count()
        lead = serializer.save(user=self.request.user, order=last_order)
        ActivityLog.objects.create(
            user=self.request.user,
            pipeline_lead=lead,
            action=f"Added to pipeline in stage '{stage.name}'"
        )

class PipelineLeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PipelineLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PipelineLead.objects.filter(
            user=self.request.user
        ).select_related('lead', 'stage').prefetch_related('logs')
    
    def perform_destroy(self, instance):
        ActivityLog.objects.create(
            user=self.request.user,
            pipeline_lead=None,
            action=f"Lead '{instance.lead.name}' removed from pipeline"
        )
        instance.delete()

class PipelineLeadMoveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            lead = PipelineLead.objects.select_related('stage').get(pk=pk, user=request.user)
        except PipelineLead.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        
        new_stage_id = request.data.get('stage_id')
        new_order = request.data.get('order', lead.order)
        
        try:
            new_stage = PipelineStage.objects.get(id=new_stage_id, user=request.user)
        except PipelineStage.DoesNotExist:
            return Response({"error": "Stage not found."}, status=status.HTTP_400_BAD_REQUEST)

        old_stage_name = lead.stage.name
        if lead.stage != new_stage:
            lead.stage = new_stage
            ActivityLog.objects.create(
                user=request.user,
                pipeline_lead=lead,
                action=f"Moved from '{old_stage_name}' to '{new_stage.name}'"
            )
            
        lead.order = new_order
        lead.save()
        return Response(PipelineLeadSerializer(lead).data)

class PipelineStageListCreateView(generics.ListCreateAPIView):
    serializer_class = PipelineStageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PipelineStage.objects.filter(user=self.request.user).order_by('order')

    def perform_create(self, serializer):
        last_order = PipelineStage.objects.filter(user=self.request.user).count()
        serializer.save(user=self.request.user, order=last_order + 1)

class PipelineStageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PipelineStageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PipelineStage.objects.filter(user=self.request.user)
        
    def perform_destroy(self, instance):
        if instance.system_key:
            raise serializers.ValidationError("Cannot delete a system stage.")
        if instance.leads.exists():
            raise serializers.ValidationError("Cannot delete a stage that contains leads.")
        instance.delete()

class PipelineStageReorderView(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request):
        stages = request.data.get('stages', [])
        if not stages:
            return Response({"status": "reordered"})

        # Single SELECT + single bulk UPDATE instead of N individual UPDATEs
        stage_ids = [item['id'] for item in stages]
        order_map = {item['id']: item['order'] for item in stages}
        stage_objs = list(
            PipelineStage.objects.filter(id__in=stage_ids, user=request.user)
        )
        for obj in stage_objs:
            obj.order = order_map[obj.id]
        PipelineStage.objects.bulk_update(stage_objs, ['order'])
        return Response({"status": "reordered"})


class Echo:
    """Write-only pseudo-buffer for csv.writer to stream rows."""
    def write(self, value):
        return value


class CSVExportView(APIView):
    """
    GET /api/pipeline/export/csv/
    Exports all pipeline leads as a downloadable CSV file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        leads = PipelineLead.objects.filter(
            user=request.user
        ).select_related('lead', 'stage').order_by('stage__order', 'order')

        def csv_rows():
            writer = csv.writer(Echo())
            yield writer.writerow([
                'Lead Name', 'Niche', 'City', 'Country', 'Website',
                'Phone', 'Email', 'Stage', 'Deal Value',
                'Follow-up Date', 'Notes', 'Created At'
            ])
            for pl in leads:
                yield writer.writerow([
                    pl.lead.name,
                    pl.lead.niche,
                    pl.lead.city,
                    pl.lead.country,
                    pl.lead.website or '',
                    pl.lead.phone or '',
                    pl.lead.email or '',
                    pl.stage.name,
                    str(pl.deal_value),
                    str(pl.follow_up_date or ''),
                    pl.notes,
                    pl.created_at.strftime('%Y-%m-%d %H:%M'),
                ])

        response = StreamingHttpResponse(csv_rows(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pipeline_export.csv"'
        return response
