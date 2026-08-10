"""SAP backend connectors (abstracted, safely mocked by default).

Each connector exposes a clean interface. Real implementations (pyrfc,
sap-cf-destination, python-sap-cloud-connector, sap-gui-scripting) can be
plugged behind the same protocol without changes to the agents.
"""

from .rfc_connector import RFCConnector, build_rfc_connector
from .odata_connector import ODataConnector, build_odata_connector
from .sap_gui_automation import SAPGuiAutomation, build_sap_gui_automation
from .cloud_connector import CloudConnector, build_cloud_connector

__all__ = [
    "RFCConnector",
    "build_rfc_connector",
    "ODataConnector",
    "build_odata_connector",
    "SAPGuiAutomation",
    "build_sap_gui_automation",
    "CloudConnector",
    "build_cloud_connector",
]