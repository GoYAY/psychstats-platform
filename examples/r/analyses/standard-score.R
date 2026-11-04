source("examples/r/analyses/_common.R")
d <- read_data("cross_sectional_survey")
z <- as.numeric(scale(d$stress))
emit(c(z_mean=mean(z), z_sd=sd(z), first_z=z[1]))
