source("_common.R")
set.seed(4601); x <- rnorm(70,70,8); n <- length(x); df <- n-1
variance <- var(x); ci <- df*variance/qchisq(c(0.975,0.025),df)
print(c(variance=variance,variance_lower=ci[1],variance_upper=ci[2],sd=sd(x)))
finish(c(variance=variance,ci_lower=ci[1],ci_upper=ci[2],sd_lower=sqrt(ci[1]),sd_upper=sqrt(ci[2]),n=n))

