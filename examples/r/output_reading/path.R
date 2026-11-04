source("_common.R")
d <- read.csv("cross_sectional_survey.csv")
model <- 'social_support ~ a*stress
well_being ~ b*social_support+c*stress'
fit <- lavaan::sem(model,d)
check_sem(fit); print(summary(fit,fit.measures=TRUE,standardized=TRUE))
pe <- lavaan::parameterEstimates(fit)
finish(c(a=pe$est[pe$label=="a"],b=pe$est[pe$label=="b"],c=pe$est[pe$label=="c"],df=unname(lavaan::fitMeasures(fit,"df"))),sem_tables(fit))
