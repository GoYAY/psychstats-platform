source("examples/r/analyses/_common.R")
d <- read_data("learning_experiment")
a <- d$gain[d$condition=="retrieval"]; b <- d$gain[d$condition=="control"]
pooled <- sqrt(((length(a)-1)*var(a)+(length(b)-1)*var(b))/(length(a)+length(b)-2))
emit(c(cohens_d=(mean(a)-mean(b))/pooled, pooled_sd=pooled))
