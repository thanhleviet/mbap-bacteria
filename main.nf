params.input = null
params.outdir = null

process FASTP {
    
    publishDir "${params.outdir}/${sample_id}/reads-qc", mode: 'copy'

    label "fastp"
    
    time { 1.hour * task.attempt }

    conda 'bioconda::fastp:0.24.0'

    container 'community.wave.seqera.io/library/fastp:0.24.0--62c97b06e8447690'

    tag {sample_id}
    
    cpus { 1 * task.attempt }

    memory { 2.GB * task.attempt }

    errorStrategy { task.exitStatus in 137..140 ? 'retry' : 'terminate' }

    maxRetries 3

    input:
    tuple val(sample_id), path(fastqs)
    
    output:
    tuple val(sample_id), path("${sample_id}.fastp.json"), emit: logs
    
    script:
    """
    fastp -i ${fastqs[0]} \
    -I ${fastqs[1]} \
    -j fastp.json \
    -w ${task.cpus}
    mv fastp.json ${sample_id}.fastp.json
    """
}

workflow {
    ch_input = Channel.fromPath(params.input, checkIfExists: true)
                      .splitCsv(header: true, quote: '"')
                      .map {row -> tuple(row.sample, [row.fastq_1, row.fastq_2])}
    FASTP(ch_input)
}
