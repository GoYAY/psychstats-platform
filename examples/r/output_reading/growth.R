source("_common.R")
set.seed(4501)
n <- 240; intercept <- rnorm(n,55,5); slope <- rnorm(n,1.5,0.8)
d <- as.data.frame(sapply(0:3,function(t)intercept+slope*t+rnorm(n,sd=2))); names(d) <- paste0("y",0:3)
model <- 'i =~ 1*y0+1*y1+1*y2+1*y3
s =~ 0*y0+1*y1+2*y2+3*y3'
fit <- lavaan::growth(model,d)
check_sem(fit); print(summary(fit,fit.measures=TRUE,standardized=TRUE)); pe <- lavaan::parameterEstimates(fit)
finish(c(intercept_mean=pe$est[pe$lhs=="i"&pe$op=="~1"],slope_mean=pe$est[pe$lhs=="s"&pe$op=="~1"],slope_variance=pe$est[pe$lhs=="s"&pe$rhs=="s"&pe$op=="~~"],cfi=unname(lavaan::fitMeasures(fit,"cfi"))),sem_tables(fit))

