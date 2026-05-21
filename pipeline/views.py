import csv
from django.db.models import Prefetch, Sum
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        base_qs = PipelineLead.objects.filter(user=request.user)
        total_value = base_qs.aggregate(Sum('deal_value'))['deal_value__sum'] or 0.00
        won_value = base_qs.filter(stage__system_key='closed_won').aggregate(Sum('deal_value'))['deal_value__sum'] or 0.00
        total_leads = base_qs.count()
        won_leads = base_qs.filter(stage__system_key='closed_won').count()
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
        return PipelineLead.objects.filter(user=self.request.user)

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
        return PipelineLead.objects.filter(user=self.request.user)
    
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
            lead = PipelineLead.objects.get(pk=pk, user=request.user)
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
        for item in stages:
            PipelineStage.objects.filter(id=item['id'], user=request.user).update(order=item['order'])
        return Response({"status": "reordered"})
