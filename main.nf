params.uuid = null
params.input = null // E.g: s3://path/to/fastq.file
params.outdir = null // outdir is the parental location of the input E.g: s3://path/to/

process FASTP {
    
    publishDir "${params.outdir}", mode: 'copy'

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
    path(fastq)
    
    output:
    path("${fastq.baseName}.fastp.json"), emit: logs
    
    script:

    """
    fastp -i ${fastq} \
    -j fastp.json \
    -w ${task.cpus}
    mv fastp.json ${fastq.baseName}.fastp.json
    """
}

workflow {
    ch_input = Channel.fromPath(params.input, checkIfExists: true)
    FASTP(ch_input)
}
