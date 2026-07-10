from django.urls import path
from pipeline.views import (
    BoardView, StatsView, 
    PipelineLeadListCreateView, PipelineLeadDetailView, PipelineLeadMoveView,
    PipelineStageListCreateView, PipelineStageDetailView, PipelineStageReorderView,
    CSVExportView,
)

urlpatterns = [
    path('board/', BoardView.as_view(), name='pipeline-board'),
    path('stats/', StatsView.as_view(), name='pipeline-stats'),
    
    path('leads/', PipelineLeadListCreateView.as_view(), name='pipeline-lead-list'),
    path('leads/<int:pk>/', PipelineLeadDetailView.as_view(), name='pipeline-lead-detail'),
    path('leads/<int:pk>/stage/', PipelineLeadMoveView.as_view(), name='pipeline-lead-move'),
    
    path('stages/', PipelineStageListCreateView.as_view(), name='pipeline-stage-list'),
    path('stages/reorder/', PipelineStageReorderView.as_view(), name='pipeline-stage-reorder'),
    path('stages/<int:pk>/', PipelineStageDetailView.as_view(), name='pipeline-stage-detail'),

    path('export/csv/', CSVExportView.as_view(), name='pipeline-export-csv'),
]

