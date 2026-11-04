source("_common.R")
set.seed(4305)
n <- 600; x <- rnorm(n); z <- rnorm(n)
rhs <- cbind(0.7*x+rnorm(n),0.8*z+rnorm(n))
Y <- rhs%*%t(solve(matrix(c(1,-0.25,-0.2,1),2,byrow=TRUE)))
d <- data.frame(x,z,y1=Y[,1],y2=Y[,2])
model <- 'y1 ~ a*y2+c*x
y2 ~ b*y1+d*z
y1 ~~ y2'
fit <- lavaan::sem(model,d,fixed.x=FALSE)
check_sem(fit); print(summary(fit,fit.measures=TRUE))
pe <- lavaan::parameterEstimates(fit); a <- pe$est[pe$label=="a"]; b <- pe$est[pe$label=="b"]
stopifnot(abs(a*b)<1)
finish(c(a=a,b=b,feedback_product=a*b,df=unname(lavaan::fitMeasures(fit,"df"))),sem_tables(fit))
