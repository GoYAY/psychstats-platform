source("examples/r/analyses/_common.R")
d <- read_data("messy_survey")
missing <- colSums(is.na(d) | d == "")
emit(c(stress_missing=as.numeric(missing["stress"]), age_missing=as.numeric(missing["age_text"]), rows=nrow(d)))
