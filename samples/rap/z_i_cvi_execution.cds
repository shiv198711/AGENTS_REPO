// -----------------------------------------------------------------------
// Sample RAP CDS view — CVI/MDS Note Execution root entity
// Namespace: Z_CVI_AUTO
// Consumed by the Fiori Elements / freestyle UI on SAP BTP ABAP env.
// -----------------------------------------------------------------------

@AccessControl.authorizationCheck: #CHECK
@EndUserText.label: 'CVI/MDS Note Execution (RAP root)'
@Metadata.allowExtensions: true
define root view entity Z_I_CVI_EXECUTION
  as select from zcvi_execution as Execution
{
  key   execution_id                     as ExecutionId,
        system_type                      as SystemType,
        system_tier                      as SystemTier,
        status                           as Status,
        requested_by                     as RequestedBy,
        started_at                       as StartedAt,
        finished_at                      as FinishedAt,
        error_summary                    as ErrorSummary,
        rollback_recommendation          as RollbackRecommendation,

        // associations
        _Notes,
        _Transports,
        _CockpitResults
}