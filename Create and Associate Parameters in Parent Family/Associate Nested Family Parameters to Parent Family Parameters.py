import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

clr.AddReference('RevitNodes')
import Revit
clr.ImportExtensions(Revit.GeometryConversion)
clr.ImportExtensions(Revit.Elements)

clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# Get current document
doc = DocumentManager.Instance.CurrentDBDocument

# Get inputs
element = IN[0]  # Family instance
epSearch = IN[1]  # Parameter names to search for in element or type parameters
fpSearch = IN[2]  # Parameter names to find in the family

# Ensure search parameters are lists
if not isinstance(epSearch, list):
    epSearch = [epSearch]
if not isinstance(fpSearch, list):
    fpSearch = [fpSearch]

# Unwrap the element
element = UnwrapElement(element)

# Create a parameter dictionary for the family parameters
famParams = doc.FamilyManager.Parameters
fpDict = {}
for fp in famParams:
    fpDict[fp.Definition.Name] = fp

# Find all element parameters - combining instance and type
elemParams = element.Parameters
elemType = element.Symbol
typeParams = elemType.Parameters

# Combined parameter dictionary
epDict = {}
# Add instance parameters first
for ep in elemParams:
    epDict[ep.Definition.Name] = ep
# Add type parameters (will override instance if there's duplication)
for tp in typeParams:
    epDict[tp.Definition.Name] = tp

# Create parameter associations
TransactionManager.Instance.EnsureInTransaction(doc)

error_reports = []
success_count = 0
visibility_params_found = []

for i in range(min(len(epSearch), len(fpSearch))):
    ep_name = epSearch[i]
    fp_name = fpSearch[i]
    
    # Look up parameters
    elem_param = epDict.get(ep_name)
    fam_param = fpDict.get(fp_name)
    
    # Check if parameters were found
    if elem_param is None:
        error_reports.append(f"Parameter '{ep_name}' not found in instance or type")
        continue
        
    if fam_param is None:
        error_reports.append(f"Family parameter '{fp_name}' not found")
        continue
    
    # Try to associate parameters
    try:
        doc.FamilyManager.AssociateElementParameterToFamilyParameter(elem_param, fam_param)
        error_reports.append(f"Successfully associated '{ep_name}' to '{fp_name}'")
        success_count += 1
        
        # Keep track of visibility parameters
        if "visibility" in ep_name.lower() or "show" in ep_name.lower() or "hidden" in ep_name.lower():
            visibility_params_found.append((ep_name, elem_param))
    except Exception as ex:
        error_reports.append(f"Error associating '{ep_name}' to '{fp_name}': {str(ex)}")

# Set visibility parameters to true (1)
visibility_param_status = []
for param_name, param in visibility_params_found:
    try:
        # Check if it's an instance parameter (we only want to set instance parameters)
        param_is_instance = False
        for ep in elemParams:
            if ep.Definition.Name == param_name:
                param_is_instance = True
                break
                
        if param_is_instance:
            if param.StorageType == StorageType.Integer:
                param.Set(1)  # 1 typically means "visible" or "true"
                visibility_param_status.append(f"Set '{param_name}' to 1 (visible)")
            elif param.StorageType == StorageType.String:
                param.Set("True")
                visibility_param_status.append(f"Set '{param_name}' to 'True'")
            else:
                visibility_param_status.append(f"Couldn't set '{param_name}' - unknown storage type")
        else:
            visibility_param_status.append(f"Skipped '{param_name}' - not an instance parameter")
    except Exception as ex:
        visibility_param_status.append(f"Error setting '{param_name}': {str(ex)}")

TransactionManager.Instance.TransactionTaskDone()

# Debug information
debug_info = {
    "Available Family Parameters": [fp.Definition.Name for fp in famParams],
    "Requested Element Parameters": epSearch,
    "Requested Family Parameters": fpSearch,
    "Success Count": success_count,
    "Visibility Parameters Found": [name for name, _ in visibility_params_found],
    "Visibility Parameter Settings": visibility_param_status
}

# Output results
OUT = element, error_reports, debug_info
