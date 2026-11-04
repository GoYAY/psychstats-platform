source("_common.R")
d <- read.csv("cross_sectional_survey.csv")
x <- d$stress[!is.na(d$stress)]
print(summary(x))
print(c(n=length(x), mean=mean(x), sd=sd(x), median=median(x), IQR=IQR(x)))
finish(c(n=length(x), mean=mean(x), sd=sd(x), median=median(x), iqr=IQR(x)))
