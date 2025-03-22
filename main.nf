params.uuid = null // sample hash
params.input = null // a CSV file
params.outdir = null // outdir is the parental location of the input E.g: s3://path/to/
params.ai_summary = false
params.logo = "${projectDir}/assets/theiagen.png"

process FASTP {
    
    // publishDir "${params.outdir}", mode: 'copy'

    label "fastp"
    label "no_publish"

    time { 1.hour * task.attempt }

    conda 'bioconda::fastp:0.24.0'

    container 'community.wave.seqera.io/library/fastp:0.24.0--62c97b06e8447690'

    tag "${sample_id}"
    
    cpus { 1 * task.attempt }

    memory { 2.GB * task.attempt }

    errorStrategy { task.exitStatus in 137..140 ? 'retry' : 'terminate' }

    maxRetries 3

    input:
    tuple val(sample_id), path(fastq1), path(fastq2)
    
    output:
    tuple val(sample_id), path("R1.fastq.gz"), path("R2.fastq.gz"), emit: fastq
    
    script:
    """
    fastp -i ${fastq1} \
    -I ${fastq2} \
    -o R1.fastq.gz \
    -O R2.fastq.gz \
    -w ${task.cpus}
    """
}

process ASSEMBLY {
    label "CHANGE_ME"
    
    container 'community.wave.seqera.io/library/shovill:1.1.0--bbe6c56d0056ba59'
    
    tag {sample_id}

    cpus 4
    memory '16.GB'

    input:
    tuple val(sample_id), path(forward), path(reverse)
    output:
    tuple val(sample_id), path("${sample_id}.fa"), emit: contigs

    script:
    """
    shovill --cpus ${task.cpus} --R1 ${forward} --R2 ${reverse} --outdir output
    cp output/contigs.fa ${sample_id}.fa
    """
}

process SPECIATION {
    
    label "CHANGE_ME"
    label "no_publish"

    container 'community.wave.seqera.io/library/bbmap:39.19--5d565ac4b6e1993c'

    tag {sample_id}
    
    cpus 2

    input:
    tuple val(sample_id), path(contigs)
    output:
    path("${sample_id}.tsv")

    script:
    """
    sendsketch.sh in=${contigs} nt out=output.tsv
    head -n 4 output.tsv | tail -n 2 | awk 'BEGIN {FS="\t"; OFS="\t"} 
    NR==1 {print "Sample_ID", \$0} NR>1 {print "${sample_id}", \$0}' > ${sample_id}.tsv
    """
}

process AMR_ABRICATE {
    
    label "CHANGE_ME"

    container 'staphb/abricate:1.0.1-vibrio-cholera'
    
    tag {"RUNNING"}
    
    cpus 2
    memory '4.GB'

    input:
    path(contigs)
    
    output:
    path("amr_abricate.tsv")

    script:
    """
    abricate --db card ${contigs} > amr_abricate.tsv
    """
}

process AMR_FINDER {
    
    label "CHANGE_ME"
    label "no_publish"

    container 'ncbi/amr:4.0.19-2024-12-18.1'

    tag {sample_id}
    
    cpus 4

    input:
    tuple val(sample_id), path(contigs)
    
    output:
    path("${sample_id}.amr_finder.tsv")

    script:
    """
    amrfinder --name ${sample_id} -n ${contigs} --threads ${task.cpus} -o ${sample_id}.amr_finder.tsv
    """
}

process MLST {

    label "CHANGE_ME"

    container 'staphb/mlst:2.23.0-2024-12-31'

    cpus 2
    memory '4.GB'
    
    input:
    path(contigs)
    
    output:
    path("mlst.tsv")

    script:
    """
    mlst --nopath ${contigs} > output.tsv
    echo -e "Sample\tSpecies\tST\tAllele1\tAllele2\tAllele3\tAllele4\tAllele5\tAllele6\tAllele7" > header.txt && cat header.txt output.tsv > mlst.tsv
    """
}

process MULTIQC {
    
    label "CHANGE_ME"
    
    container 'community.wave.seqera.io/library/awscli_pip_multiqc:6acedd3980be93c9'

    tag {"Reporting"}
    
    cpus 2

    input:
    path(input_files)
    path(logo)
    
    output:
    path("report.html")
    
    script:
    def ai = params.ai_summary ? "--ai-summary-full" : ""
    """
    for file in ${input_files}; do
    # Extract the base name and extension
    base=\${file%.*}
    ext=\${file##*.}
    
    # Create the new filename with _mqc added
    new_name="\${base}_mqc.\${ext}"
    
    # Rename the file.
    mv "\$file" "\$new_name"
    done

    cat > multiqc_config.yaml << 'EOF'
    title: "theiaMBAP Report"
    subtitle: "Bacteria Pipeline"
    intro_text: "MultiQC reports summarise analysis results."
    show_analysis_paths: False
    show_analysis_time: False
    custom_logo: ${logo}
    custom_logo_url: "https://www.theiagen.com"
    custom_logo_title: "Theiagen Genomics"
    custom_content:
      output_type: 'table'
    report_section_order:
      amr_abricate:
        order: 1
      amr_finder:
        order: 2
      mlst:
        order: 3
      speciation:
        order: 10
    EOF

    export AI_REPORT=\$([ -n "\${TOWER_ACCESS_TOKEN+x}" ] && echo "--ai-summary-full" || echo "")

    multiqc -c multiqc_config.yaml --filename report \${AI_REPORT} .
    """
}

workflow {
    ch_input = Channel.fromPath(params.input, checkIfExists: true)
                      .splitCsv(header: true)
                      .map {it -> tuple(it.sample_id, it.fastq1, it.fastq2)}
    ch_logo = Channel.fromPath(params.logo, checkIfExists: true)
    
    FASTP(ch_input)

    ASSEMBLY(FASTP.out.fastq)
    
    ch_assembly = ASSEMBLY.out.contigs.map {it -> it[1]}.collect()
    
    SPECIATION(ASSEMBLY.out.contigs)

    MLST(ch_assembly)

    AMR_ABRICATE(ch_assembly)
    
    AMR_FINDER(ASSEMBLY.out.contigs)

    amr_finder_out = AMR_FINDER.out.collectFile(name: 'amr_finder.tsv', newLine: false, skip: 1, keepHeader:true, storeDir: params.outdir)
    
    speciation_out = SPECIATION.out.collectFile(name: 'speciation.tsv', newLine: false, skip: 1, keepHeader:true, storeDir: params.outdir)

    multiqc_in = Channel.empty()
    multiqc_in = multiqc_in.mix(MLST.out)
    multiqc_in = multiqc_in.mix(AMR_ABRICATE.out)
    multiqc_in = multiqc_in.mix(amr_finder_out)
    multiqc_in = multiqc_in.mix(speciation_out)

    MULTIQC(multiqc_in.collect(), ch_logo)
}
