#!/usr/bin/env python3

import os
import pandas as pd
import re
import argparse

def clean_sample_id(sample_id):
    """Remove .fa extension if present to match IDs in the Newick tree file."""
    return sample_id.replace('.fa', '')

def process_mlst_data(file_path):
    """Process MLST data."""
    mlst_df = pd.read_csv(file_path, sep='\t')
    # Clean sample IDs by removing .fa extension
    mlst_df['Sample'] = mlst_df['Sample'].apply(clean_sample_id)
    # Rename column to match tree
    mlst_df = mlst_df.rename(columns={'Sample': 'id'})
    return mlst_df

def process_amr_finder(file_path):
    """Process AMR Finder data, consolidating genes by sample."""
    amr_finder_df = pd.read_csv(file_path, sep='\t')
    
    # Group by sample and aggregate AMR genes and classes
    amr_genes = {}
    amr_classes = {}
    
    for _, row in amr_finder_df.iterrows():
        sample = row['Name']
        gene = row['Element symbol']
        amr_class = row['Class']
        
        if sample not in amr_genes:
            amr_genes[sample] = []
            amr_classes[sample] = set()
        
        amr_genes[sample].append(gene)
        amr_classes[sample].add(amr_class)
    
    # Create dataframe with consolidated AMR data
    amr_df = pd.DataFrame({
        'id': list(amr_genes.keys()),
        'AMR_genes': [', '.join(genes) for genes in amr_genes.values()],
        'AMR_classes': [', '.join(classes) for classes in amr_classes.values()]
    })
    
    return amr_df

def process_amr_abricate(file_path):
    """Process AMR Abricate data, consolidating resistance by sample."""
    # Read the file with the first line as header, even if it starts with #
    with open(file_path, 'r') as f:
        header_line = f.readline().strip()
    
    # Parse header line to get column names
    if header_line.startswith('#'):
        header_line = header_line[1:]  # Remove the # character
    column_names = header_line.split('\t')
    
    # Now read the file with pandas, skipping the first line and using the parsed column names
    amr_abricate_df = pd.read_csv(file_path, sep='\t', skiprows=1, names=column_names)
    
    # Extract sample IDs from FILE column (removing .fa extension)
    file_column = column_names[0]  # First column is the FILE column
    amr_abricate_df['sample_id'] = amr_abricate_df[file_column].apply(lambda x: x.split('.fa')[0])
    
    # Find the correct column names for GENE and RESISTANCE
    gene_column = next((col for col in column_names if col.upper() == 'GENE'), None)
    resistance_column = next((col for col in column_names if col.upper() == 'RESISTANCE'), None)
    
    if not gene_column or not resistance_column:
        print("Warning: Could not find GENE or RESISTANCE columns in abricate file")
        return pd.DataFrame(columns=['id', 'resistance_phenotypes', 'abricate_genes'])
    
    # Group by sample and aggregate resistance phenotypes
    resistance_phenotypes = {}
    genes = {}
    
    for _, row in amr_abricate_df.iterrows():
        sample = row['sample_id']
        resistance = row[resistance_column].split(';')
        gene = row[gene_column]
        
        if sample not in resistance_phenotypes:
            resistance_phenotypes[sample] = set()
            genes[sample] = set()
        
        resistance_phenotypes[sample].update(resistance)
        genes[sample].add(gene)
    
    # Create dataframe with consolidated resistance data
    abricate_df = pd.DataFrame({
        'id': list(resistance_phenotypes.keys()),
        'resistance_phenotypes': [', '.join(sorted(r)) for r in resistance_phenotypes.values()],
        'abricate_genes': [', '.join(sorted(g)) for g in genes.values()]
    })
    
    return abricate_df

def process_speciation(file_path):
    """Process speciation data."""
    speciation_df = pd.read_csv(file_path, sep='\t')
    # Rename column to match tree
    speciation_df = speciation_df.rename(columns={'Sample_ID': 'id'})
    return speciation_df

def transform_amr_to_binary(dataframe):
    """
    Transform AMR categorical columns to binary presence/absence (1/0) format.
    
    Args:
        dataframe: DataFrame containing AMR categorical columns
        
    Returns:
        DataFrame with additional binary columns for AMR data
    """
    amr_columns = []
    
    # Check for AMR_classes column from AMR Finder
    if 'AMR_classes' in dataframe.columns:
        # Get unique AMR classes across all samples
        all_classes = set()
        for classes_str in dataframe['AMR_classes'].dropna():
            if classes_str:  # Check if not empty string
                classes = [cls.strip() for cls in classes_str.split(',')]
                all_classes.update(classes)
        
        # Create binary columns for each AMR class
        for amr_class in sorted(all_classes):
            col_name = f"AMR_class_{amr_class.replace(' ', '_')}"
            amr_columns.append(col_name)
            dataframe[col_name] = dataframe['AMR_classes'].apply(
                lambda x: 1 if pd.notnull(x) and amr_class in x else 0
            )
    
    # Check for AMR_genes column from AMR Finder
    if 'AMR_genes' in dataframe.columns:
        # Get unique AMR genes across all samples
        all_genes = set()
        for genes_str in dataframe['AMR_genes'].dropna():
            if genes_str:  # Check if not empty string
                genes = [gene.strip() for gene in genes_str.split(',')]
                all_genes.update(genes)
        
        # Create binary columns for each AMR gene
        for gene in sorted(all_genes):
            col_name = f"AMR_gene_{gene.replace(' ', '_')}"
            amr_columns.append(col_name)
            dataframe[col_name] = dataframe['AMR_genes'].apply(
                lambda x: 1 if pd.notnull(x) and gene in x else 0
            )
    
    # Check for resistance_phenotypes column from AMR Abricate
    if 'resistance_phenotypes' in dataframe.columns:
        # Get unique resistance phenotypes across all samples
        all_phenotypes = set()
        for phenotypes_str in dataframe['resistance_phenotypes'].dropna():
            if phenotypes_str:  # Check if not empty string
                phenotypes = [phen.strip() for phen in phenotypes_str.split(',')]
                all_phenotypes.update(phenotypes)
        
        # Create binary columns for each resistance phenotype
        for phenotype in sorted(all_phenotypes):
            col_name = f"resistance_{phenotype.replace(' ', '_')}"
            amr_columns.append(col_name)
            dataframe[col_name] = dataframe['resistance_phenotypes'].apply(
                lambda x: 1 if pd.notnull(x) and phenotype in x else 0
            )
    
    # Check for abricate_genes column from AMR Abricate
    if 'abricate_genes' in dataframe.columns:
        # Get unique abricate genes across all samples
        all_abr_genes = set()
        for genes_str in dataframe['abricate_genes'].dropna():
            if genes_str:  # Check if not empty string
                genes = [gene.strip() for gene in genes_str.split(',')]
                all_abr_genes.update(genes)
        
        # Create binary columns for each abricate gene
        for gene in sorted(all_abr_genes):
            col_name = f"abricate_gene_{gene.replace(' ', '_')}"
            amr_columns.append(col_name)
            dataframe[col_name] = dataframe['abricate_genes'].apply(
                lambda x: 1 if pd.notnull(x) and gene in x else 0
            )
    
    print(f"Added {len(amr_columns)} binary AMR presence/absence columns")
    return dataframe

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Aggregate data from multiple files for Microreact visualization")
    
    parser.add_argument('--mlst', dest='mlst_file', required=False, default='mlst.tsv',
                        help='Path to MLST TSV file (default: mlst.tsv)')
    
    parser.add_argument('--amr_finder', dest='amr_finder_file', required=False, default='amr_finder.tsv',
                        help='Path to AMR Finder TSV file (default: amr_finder.tsv)')
    
    parser.add_argument('--amr_abricate', dest='amr_abricate_file', required=False, default='amr_abricate.tsv',
                        help='Path to AMR Abricate TSV file (default: amr_abricate.tsv)')
    
    parser.add_argument('--speciation', dest='speciation_file', required=False, default='speciation.tsv',
                        help='Path to Speciation TSV file (default: speciation.tsv)')
    
    parser.add_argument('-o', '--output', dest='output_file', required=False, default='microreact_metadata.csv',
                        help='Path to output CSV file (default: microreact_metadata.csv)')
    
    parser.add_argument('-d', '--directory', dest='directory', required=False, default='.',
                        help='Base directory containing input files (default: current directory)')
    
    parser.add_argument('--binary_amr', dest='binary_amr', action='store_true',
                        help='Transform AMR data to binary presence/absence (1/0) format')
    
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Define file paths
    base_dir = args.directory
    mlst_file = os.path.join(base_dir, args.mlst_file)
    amr_finder_file = os.path.join(base_dir, args.amr_finder_file)
    amr_abricate_file = os.path.join(base_dir, args.amr_abricate_file)
    speciation_file = os.path.join(base_dir, args.speciation_file)
    
    # Check if files exist
    missing_files = []
    for file_path, file_name in [
        (mlst_file, "MLST"), 
        (amr_finder_file, "AMR Finder"), 
        (amr_abricate_file, "AMR Abricate"), 
        (speciation_file, "Speciation")
    ]:
        if not os.path.exists(file_path):
            missing_files.append(f"{file_name} file: {file_path}")
    
    if missing_files:
        print("Warning: The following files are missing:")
        for file_error in missing_files:
            print(f"  - {file_error}")
        print("Continuing with available files...")
    
    # Process each file that exists
    dfs = []
    
    if os.path.exists(mlst_file):
        mlst_df = process_mlst_data(mlst_file)
        dfs.append(mlst_df)
        print(f"Processed MLST data: {len(mlst_df)} samples")
    
    if os.path.exists(amr_finder_file):
        amr_finder_df = process_amr_finder(amr_finder_file)
        dfs.append(amr_finder_df)
        print(f"Processed AMR Finder data: {len(amr_finder_df)} samples")
    
    if os.path.exists(amr_abricate_file):
        amr_abricate_df = process_amr_abricate(amr_abricate_file)
        dfs.append(amr_abricate_df)
        print(f"Processed AMR Abricate data: {len(amr_abricate_df)} samples")
    
    if os.path.exists(speciation_file):
        speciation_df = process_speciation(speciation_file)
        dfs.append(speciation_df)
        print(f"Processed Speciation data: {len(speciation_df)} samples")
    
    if not dfs:
        print("Error: No valid input files found. Exiting.")
        return
    
    # Start with the first dataframe and merge with all others
    merged_df = dfs[0]
    for df in dfs[1:]:
        merged_df = merged_df.merge(df, on='id', how='outer')
    
    # Transform AMR data to binary format (always do this now, regardless of flag)
    merged_df = transform_amr_to_binary(merged_df)
    
    # Save the merged metadata to a CSV file
    output_file = args.output_file
    merged_df.to_csv(output_file, index=False)
    
    print(f"Metadata file created: {output_file}")
    print(f"Number of samples processed: {len(merged_df)}")

if __name__ == "__main__":
    main() 