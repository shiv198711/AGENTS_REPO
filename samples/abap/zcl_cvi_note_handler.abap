*&---------------------------------------------------------------------*
*& Sample ABAP class: ZCL_CVI_NOTE_HANDLER
*&
*& Purpose:  Handler for CVI/MDS SAP Note validation & post-checks.
*&           Called from the BTP AI Agent via RFC/OData to perform
*&           system-side work that cannot be executed from BTP.
*&
*& Author :  CVI_ERROR_R_AUTO scaffold
*& Package:  Z_CVI_AUTO
*&---------------------------------------------------------------------*

CLASS zcl_cvi_note_handler DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC.

  PUBLIC SECTION.
    TYPES:
      BEGIN OF ty_note_meta,
        number    TYPE string,
        title     TYPE string,
        version   TYPE string,
        status    TYPE string,       " RELEASED | OBSOLETE
        component TYPE string,
        kind      TYPE string,       " correction | prerequisite
        manual    TYPE abap_bool,
      END OF ty_note_meta,

      BEGIN OF ty_check,
        name    TYPE string,
        status  TYPE string,          " OK | WARN | ERROR
        message TYPE string,
      END OF ty_check,
      tt_checks TYPE STANDARD TABLE OF ty_check WITH DEFAULT KEY.

    "! Validate an SAP Note against the target system.
    METHODS validate_note
      IMPORTING iv_number TYPE string
      EXPORTING es_meta   TYPE ty_note_meta
                et_checks TYPE tt_checks
                ev_valid  TYPE abap_bool.

    "! Trigger CVI_COCKPIT / MDS_LOAD_COCKPIT verification depending on
    "! the target release.
    METHODS run_post_check
      IMPORTING iv_cockpit TYPE string           " CVI_COCKPIT | MDS_LOAD_COCKPIT
      EXPORTING et_checks  TYPE tt_checks
                ev_passed  TYPE abap_bool.

    "! Auto-create a workbench transport request for this run.
    METHODS create_transport
      IMPORTING iv_text   TYPE string
      EXPORTING ev_trkorr TYPE string.

  PRIVATE SECTION.
    METHODS _add_check
      IMPORTING iv_name    TYPE string
                iv_status  TYPE string
                iv_message TYPE string
      CHANGING  ct_checks  TYPE tt_checks.

ENDCLASS.

CLASS zcl_cvi_note_handler IMPLEMENTATION.

  METHOD validate_note.
    CLEAR: es_meta, et_checks, ev_valid.
    es_meta-number = iv_number.

    " In a real implementation this would call SCWN_NOTE_READ or the
    " SNOTE API to load metadata from the local note repository.
    es_meta-title     = |CVI/MDS correction note { iv_number }|.
    es_meta-status    = 'RELEASED'.
    es_meta-component = 'CA-MDG-BP'.
    es_meta-kind      = 'correction'.
    es_meta-manual    = abap_false.

    _add_check( EXPORTING iv_name    = 'exists'
                          iv_status  = 'OK'
                          iv_message = 'Note found in local note repository'
                CHANGING  ct_checks  = et_checks ).

    _add_check( EXPORTING iv_name    = 'component_applicable'
                          iv_status  = 'OK'
                          iv_message = 'Component CA-MDG-BP is installed'
                CHANGING  ct_checks  = et_checks ).

    _add_check( EXPORTING iv_name    = 'not_already_implemented'
                          iv_status  = 'OK'
                          iv_message = 'Note not yet implemented'
                CHANGING  ct_checks  = et_checks ).

    ev_valid = abap_true.
  ENDMETHOD.

  METHOD run_post_check.
    CLEAR: et_checks, ev_passed.

    CASE iv_cockpit.
      WHEN 'CVI_COCKPIT'.
        _add_check( EXPORTING iv_name = 'business_partner_sync' iv_status = 'OK'
                              iv_message = 'BP sync green'
                    CHANGING  ct_checks = et_checks ).
        _add_check( EXPORTING iv_name = 'customer_sync' iv_status = 'OK'
                              iv_message = 'Customer sync green'
                    CHANGING  ct_checks = et_checks ).
        _add_check( EXPORTING iv_name = 'vendor_sync' iv_status = 'OK'
                              iv_message = 'Vendor sync green'
                    CHANGING  ct_checks = et_checks ).

      WHEN 'MDS_LOAD_COCKPIT'.
        _add_check( EXPORTING iv_name = 'initial_load_ready' iv_status = 'OK'
                              iv_message = 'Initial load configuration OK'
                    CHANGING  ct_checks = et_checks ).
        _add_check( EXPORTING iv_name = 'replication_ready' iv_status = 'OK'
                              iv_message = 'Replication ready'
                    CHANGING  ct_checks = et_checks ).
        _add_check( EXPORTING iv_name = 'data_consistency' iv_status = 'OK'
                              iv_message = 'BP <> Customer/Vendor consistency OK'
                    CHANGING  ct_checks = et_checks ).
      WHEN OTHERS.
        _add_check( EXPORTING iv_name = 'cockpit_unknown' iv_status = 'ERROR'
                              iv_message = |Unknown cockpit '{ iv_cockpit }'|
                    CHANGING  ct_checks = et_checks ).
    ENDCASE.

    ev_passed = COND #( WHEN line_exists( et_checks[ status = 'ERROR' ] )
                        THEN abap_false ELSE abap_true ).
  ENDMETHOD.

  METHOD create_transport.
    DATA(lv_trkorr) = |MOCKK9{ sy-uzeit }|.
    ev_trkorr = lv_trkorr.
  ENDMETHOD.

  METHOD _add_check.
    APPEND VALUE #( name    = iv_name
                    status  = iv_status
                    message = iv_message ) TO ct_checks.
  ENDMETHOD.

ENDCLASS.