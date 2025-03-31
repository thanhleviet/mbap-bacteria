#!/usr/bin/env python3

import argparse
import json
import base64
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

def encode_file_content(content: str) -> str:
    """Encode file content to base64 for inclusion in the Microreact file."""
    blob = base64.b64encode(content.encode('utf-8'))
    blob_str = str(blob)[2:-1]  # Remove b' and ' from string representation
    return blob_str

def create_file_dict(file_type: str, content: str, file_name: Optional[str] = None) -> Dict[str, Any]:
    """Create a file dictionary for inclusion in the Microreact file."""
    file_id = str(uuid.uuid4())
    
    if file_type == 'data':
        name = file_name or 'metadata.csv'
        format_type = 'text/csv'
        mimetype = 'data:application/vnd.ms-excel;base64'
    elif file_type == 'tree':
        name = file_name or 'tree.nwk'
        format_type = 'text/x-nh'
        mimetype = 'data:application/octet-stream;base64'
    else:
        raise ValueError(f"Invalid file type: {file_type}")
    
    encoded_content = encode_file_content(content)
    
    return {
        "id": file_id,
        "type": file_type,
        "name": name,
        "format": format_type,
        "blob": f"{mimetype},{encoded_content}"
    }

def create_microreact_project(
    project_name: str,
    metadata_content: str,
    tree_content: str,
    id_field_name: str = None
) -> Dict[str, Any]:
    """Create a Microreact project dictionary."""
    
    # Read the first line of metadata to get column headers
    metadata_lines = metadata_content.strip().split('\n')
    headers = metadata_lines[0].split(',')
    
    # Use the first column as the ID field if not specified
    if id_field_name is None:
        id_field_name = headers[0]
    
    # Check if id_field_name exists in headers
    if id_field_name not in headers:
        raise ValueError(f"ID field '{id_field_name}' not found in metadata headers")
    
    # Create file dictionaries
    metadata_file = create_file_dict('data', metadata_content, 'metadata.csv')
    tree_file = create_file_dict('tree', tree_content, 'tree.nwk')
    
    # Create dataset
    dataset_id = str(uuid.uuid4())
    dataset = {
        "id": dataset_id,
        "file": metadata_file["id"],
        "idFieldName": id_field_name
    }
    
    # Create table columns
    columns = []
    for header in headers:
        columns.append({
            "field": header,
            "fixed": False
        })
    
    # Create table
    table_id = str(uuid.uuid4())
    table = {
        "id": table_id,
        "title": "Metadata",
        "columns": columns,
        "file": metadata_file["id"]
    }
    
    # Create tree
    tree_id = str(uuid.uuid4())
    tree = {
        "id": tree_id,
        "file": tree_file["id"],
        "type": "rc",
        "title": "Tree",
        "labelField": id_field_name,
        "highlightedId": None,
        "showBranchLengths": False,
        "branchLengthsDigits": 4,
        "showLeafLabels": True
    }
    
    # Create project structure
    project = {
        "schema": "https://microreact.org/schema/v1.json",
        "meta": {
            "name": project_name
        },
        "datasets": {
            dataset_id: dataset
        },
        "files": {
            metadata_file["id"]: metadata_file,
            tree_file["id"]: tree_file
        },
        "tables": {
            table_id: table
        },
        "trees": {
            tree_id: tree
        },
        "charts": {},
        "filters": {},
        "maps": {},
        "networks": {},
        "notes": {},
        "panes": {},
        "slicers": {},
        "styles": {},
        "timelines": {},
        "views": {},
        "matrices": {}
    }
    
    return project

def main():
    parser = argparse.ArgumentParser(description="Generate a Microreact file with a Newick tree and CSV metadata")
    parser.add_argument("--metadata", "-m", required=True, help="Path to metadata CSV file")
    parser.add_argument("--tree", "-t", required=True, help="Path to Newick tree file")
    parser.add_argument("--output", "-o", required=True, help="Output Microreact file path")
    parser.add_argument("--name", "-n", default="Microreact Project", help="Project name")
    parser.add_argument("--id-field", "-i", help="Name of the ID field in metadata (default: first column)")
    
    args = parser.parse_args()
    
    # Read input files
    with open(args.metadata, 'r') as f:
        metadata_content = f.read()
    
    with open(args.tree, 'r') as f:
        tree_content = f.read()
    
    # Create Microreact project
    project = create_microreact_project(
        project_name=args.name,
        metadata_content=metadata_content,
        tree_content=tree_content,
        id_field_name=args.id_field
    )
    
    # Write output file
    with open(args.output, 'w') as f:
        json.dump(project, f, indent=2)
    
    print(f"Microreact file created: {args.output}")

if __name__ == "__main__":
    main()