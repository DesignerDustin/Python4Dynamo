import clr
from Autodesk.Revit.DB import *

# Import Dynamo-specific libraries
import RevitServices
from RevitServices.Persistence import DocumentManager
import re

# Get the inputs from Dynamo
param_names = IN[0]
spec_type_input = IN[1]
group_type_input = IN[2]
is_instance = IN[3]

# Make sure param_names is a list
if isinstance(param_names, str):
    param_names = [param_names]

# Ensure spec_type_input is a list of the same length as param_names
if not isinstance(spec_type_input, list):
    spec_type_input = [spec_type_input] * len(param_names)
elif len(spec_type_input) < len(param_names):
    # If spec_type_input is shorter than param_names, extend it with the last value
    spec_type_input.extend([spec_type_input[-1]] * (len(param_names) - len(spec_type_input)))

# Ensure group_type_input is a list of the same length as param_names
if not isinstance(group_type_input, list):
    group_type_input = [group_type_input] * len(param_names)
elif len(group_type_input) < len(param_names):
    # If group_type_input is shorter than param_names, extend it with the last value
    group_type_input.extend([group_type_input[-1]] * (len(param_names) - len(group_type_input)))

# Ensure is_instance is a list of the same length as param_names
if not isinstance(is_instance, list):
    is_instance = [is_instance] * len(param_names)
elif len(is_instance) < len(param_names):
    # If is_instance is shorter than param_names, extend it with the last value
    is_instance.extend([is_instance[-1]] * (len(param_names) - len(is_instance)))

# Convert string "True"/"False" to boolean if needed
for i in range(len(is_instance)):
    if isinstance(is_instance[i], str):
        is_instance[i] = is_instance[i].lower() == "true"

# Functions to convert parameter types and groups
def GetBuiltInParameterTypeId(type_name):
    """Convert parameter type name to ForgeTypeId"""
    # Check if this is already a ForgeTypeId string
    if isinstance(type_name, str) and ":" in type_name:
        try:
            return ForgeTypeId(type_name)
        except:
            pass
    
    # Common ForgeTypeId strings
    forge_type_map = {
        "autodesk.spec.aec:length-2.0.0": SpecTypeId.Double.Length,
        "autodesk.spec.aec:area-2.0.0": SpecTypeId.Double.Area,
        "autodesk.spec.aec:volume-2.0.0": SpecTypeId.Double.Volume,
        "autodesk.spec.aec:angle-2.0.0": SpecTypeId.Double.Angle,
        "autodesk.spec:text-2.0.0": SpecTypeId.String.Text,
        "autodesk.spec:integer-2.0.0": SpecTypeId.Int.Integer,
        "autodesk.spec:number-2.0.0": SpecTypeId.Double.Number,
        "autodesk.spec:yesno-2.0.0": SpecTypeId.Boolean.YesNo
    }
    
    # Common parameter type names
    type_map = {
        "Text": SpecTypeId.String.Text,
        "Integer": SpecTypeId.Int.Integer,
        "Number": SpecTypeId.Double.Number,
        "Length": SpecTypeId.Double.Length,
        "Area": SpecTypeId.Double.Area,
        "Volume": SpecTypeId.Double.Volume,
        "Angle": SpecTypeId.Double.Angle,
        "YesNo": SpecTypeId.Boolean.YesNo
    }
    
    # Clean name
    clean_name = str(type_name).strip()
    
    # Try direct match
    if clean_name in forge_type_map:
        return forge_type_map[clean_name]
    if clean_name in type_map:
        return type_map[clean_name]
    
    # Try to extract ForgeTypeId from string
    forge_match = re.search(r"(autodesk\.[^-]+:[^-]+-\d+\.\d+\.\d+)", clean_name)
    if forge_match:
        forge_id = forge_match.group(1)
        try:
            return ForgeTypeId(forge_id)
        except:
            pass
    
    # Default to Length
    return SpecTypeId.Double.Length

def GetBuiltInParameterGroupId(group_name):
    """Convert parameter group name to ForgeTypeId"""
    # Check if this is already a ForgeTypeId string
    if isinstance(group_name, str) and ":" in group_name:
        try:
            return ForgeTypeId(group_name)
        except:
            pass
    
    # Common ForgeTypeId strings
    forge_group_map = {
        "autodesk.parameter.group:general-2.0.0": GroupTypeId.General,
        "autodesk.parameter.group:dimensions-2.0.0": GroupTypeId.Dimensions,
        "autodesk.parameter.group:identity_data-2.0.0": GroupTypeId.IdentityData,
        "autodesk.parameter.group:geometry-2.0.0": GroupTypeId.Geometry,
        # Add -1.0.0 versions as well
        "autodesk.parameter.group:general-1.0.0": GroupTypeId.General,
        "autodesk.parameter.group:dimensions-1.0.0": GroupTypeId.Dimensions,
        "autodesk.parameter.group:identity_data-1.0.0": GroupTypeId.IdentityData,
        "autodesk.parameter.group:geometry-1.0.0": GroupTypeId.Geometry,
    }
    
    # Common parameter group names
    group_map = {
        "PG_GENERAL": GroupTypeId.General,
        "General": GroupTypeId.General,
        "PG_IDENTITY_DATA": GroupTypeId.IdentityData,
        "Identity Data": GroupTypeId.IdentityData,
        "PG_GEOMETRY": GroupTypeId.Geometry,
        "Geometry": GroupTypeId.Geometry,
        "PG_DIMENSIONS": GroupTypeId.Dimensions,
        "Dimensions": GroupTypeId.Dimensions
    }
    
    # Clean name
    clean_name = str(group_name).strip()
    
    # Try direct match
    if clean_name in forge_group_map:
        return forge_group_map[clean_name]
    if clean_name in group_map:
        return group_map[clean_name]
    
    # Try to extract ForgeTypeId from string
    forge_match = re.search(r"(autodesk\.[^-]+:[^-]+-\d+\.\d+\.\d+)", clean_name)
    if forge_match:
        forge_id = forge_match.group(1)
        try:
            return ForgeTypeId(forge_id)
        except:
            pass
    
    # Default to Dimensions
    return GroupTypeId.Dimensions

# Handle input types
def get_type_id(input_obj):
    """Extract ForgeTypeId from various input types"""
    if isinstance(input_obj, str) and ":" in input_obj:
        # Direct ForgeTypeId string
        return input_obj
    elif isinstance(input_obj, list) and len(input_obj) > 0:
        # Check if list contains ForgeTypeId strings
        for item in input_obj:
            if isinstance(item, str) and ":" in item:
                return item
        # Use first item
        return input_obj[0]
    else:
        # Use as is
        return input_obj

# Main function to add parameters
def add_family_parameters(doc, param_names, spec_type_inputs, group_type_inputs, is_instance_list):
    """Add family parameters to the document"""
    results = []
    added_params = []
    
    # Check if we're in a family document
    if not doc.IsFamilyDocument:
        return ["Error: This script can only be run in the Family Editor."], []
    
    # Get the family manager
    family_manager = doc.FamilyManager
    
    # Create a transaction directly
    transaction = Transaction(doc, "Add Family Parameters")
    
    try:
        # Start the transaction
        transaction.Start()
        
        # Add each parameter with its own type
        for i, param_name in enumerate(param_names):
            # Get the specific type and group for this parameter
            spec_type_obj = get_type_id(spec_type_inputs[i])
            spec_type_id = GetBuiltInParameterTypeId(spec_type_obj)
            
            group_type_obj = get_type_id(group_type_inputs[i])
            group_type_id = GetBuiltInParameterGroupId(group_type_obj)
            
            # Get the specific instance setting for this parameter
            is_instance_param = is_instance_list[i]
            
            # Check if already exists
            existing_param = None
            try:
                existing_param = family_manager.get_Parameter(param_name)
            except:
                pass
            
            if existing_param is not None:
                continue
            
            # Add parameter
            try:
                new_param = family_manager.AddParameter(param_name, group_type_id, spec_type_id, is_instance_param)
                if new_param is not None:
                    added_params.append(param_name)
            except:
                pass
        
        # Commit the transaction
        transaction.Commit()
        
    except:
        # Roll back the transaction
        if transaction.HasStarted() and not transaction.HasEnded():
            transaction.RollBack()
    
    return added_params

# Get current document
doc = DocumentManager.Instance.CurrentDBDocument

# Call the function with all inputs
added_params = add_family_parameters(doc, param_names, spec_type_input, group_type_input, is_instance)

# Return just the successfully added parameter names
OUT = added_params
