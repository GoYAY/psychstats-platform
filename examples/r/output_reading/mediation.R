source("_common.R")
set.seed(4401)
d <- read.csv("cross_sectional_survey.csv")
model <- 'social_support ~ a*stress
well_being ~ b*social_support+c*stress
indirect := a*b
total := c+a*b'
fit <- lavaan::sem(model,d,se="bootstrap",bootstrap=300)
check_sem(fit); print(summary(fit,standardized=TRUE))
pe <- lavaan::parameterEstimates(fit,boot.ci.type="perc")
r <- pe[pe$lhs=="indirect" & pe$op==":=",]
finish(c(indirect=r$est,ci_lower=r$ci.lower,ci_upper=r$ci.upper,direct=pe$est[pe$label=="c"]),list(parameters=pe))

