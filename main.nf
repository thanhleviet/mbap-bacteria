params.uuid = null // sample hash
params.input = null // a CSV file
params.outdir = null // outdir is the parental location of the input E.g: s3://path/to/

process FASTP {
    
    // publishDir "${params.outdir}", mode: 'copy'

    label "fastp"
    
    time { 1.hour * task.attempt }

    conda 'bioconda::fastp:0.24.0'

    container 'community.wave.seqera.io/library/fastp:0.24.0--62c97b06e8447690'

    tag "${params.uuid}"
    
    cpus { 1 * task.attempt }

    memory { 2.GB * task.attempt }

    errorStrategy { task.exitStatus in 137..140 ? 'retry' : 'terminate' }

    maxRetries 3

    input:
    tuple val(sample_id), path(fastq1), path(fastq2)
    
    output:
    tuple val(sample_id), path("R1.fastq.gz"), path("R2.fastq.gz")
    
    script:

    """
    fastp -i ${fastq1} \
    -I ${fastq2}
    -o R1.fastq.gz
    -O R2.fastq.gz
    -w ${task.cpus}
    """
}

process ASSEMBLY {
    publishDir "${params.outdir}", mode: 'copy'

    label "CHANGE_ME"
    
    container 'community.wave.seqera.io/library/shovill:1.1.0--bbe6c56d0056ba59'
    
    tag {sample_id}

    cpus 4
    memory '16.GB'

    input:
    tuple val(sample_id), path(forward), path(reverse)
    output:
    tuple val(sample_id), path("output/contigs.fa"), emit: contigs

    script:
    """
    shovill --cpus ${task.cpus} --trim --R1 ${forward} --R2 ${reverse} --outdir output
    """
}

process AMR_ABRICATE {
    
    label "CHANGE_ME"
    container 'staphb/abricate:1.0.1-vibrio-cholera'
    
    tag {sample_id}
    
    cpus 4

    input:
    tuple val(sample_id), path(contigs)
    
    output:
    tuple path("amr.tsv")

    script:
    """
    abricate --db card ${contigs} > amr.tsv
    """
}

workflow {
    ch_input = Channel.fromPath(params.input, checkIfExists: true)
                      .splitCsv(header: true)
                      .map {it -> tuple(it.sample_id, it.fastq1, it.fastq2)}

    FASTP(ch_input)

    ASSEMBLY(FASTP.out.fastq)

    AMR_ABRICATE(ASSEMBLY.out.contigs)
}
