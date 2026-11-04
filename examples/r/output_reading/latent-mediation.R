source("_common.R")
d <- latent_teaching(450,4402)
model <- paste(measurement_model,'f2 ~ a*f1
f3 ~ b*f2+c*f1
indirect := a*b',sep="\n")
fit <- lavaan::sem(model,d)
check_sem(fit); print(summary(fit,fit.measures=TRUE,standardized=TRUE))
pe <- lavaan::parameterEstimates(fit); r <- pe[pe$op==":=" & pe$lhs=="indirect",]
finish(c(indirect=r$est,se=r$se,ci_lower=r$ci.lower,ci_upper=r$ci.upper,cfi=unname(lavaan::fitMeasures(fit,"cfi"))),sem_tables(fit))

