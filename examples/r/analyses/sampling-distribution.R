source("examples/r/analyses/_common.R")
set.seed(120)
means <- replicate(2000,mean(rnorm(40,mean=50,sd=10)))
emit(c(mean_of_means=mean(means), sd_of_means=sd(means), theoretical_se=10/sqrt(40)))
