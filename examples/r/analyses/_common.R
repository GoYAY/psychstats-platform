if (.Platform$OS.type == "windows") suppressWarnings(Sys.setlocale("LC_ALL", "Chinese"))
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("usage: Rscript analysis.R metrics.tsv data_dir")
out_path <- args[[1]]
data_dir <- args[[2]]
read_data <- function(name) read.csv(file.path(data_dir, paste0(name, ".csv")), stringsAsFactors = FALSE)
emit <- function(values) {
  if (is.null(names(values)) || any(!is.finite(values))) stop("metrics must be named finite numbers")
  write.table(data.frame(metric=names(values), value=as.numeric(values)), out_path,
              sep="\t", row.names=FALSE, quote=FALSE)
}
