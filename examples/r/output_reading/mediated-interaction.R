source("_common.R")
set.seed(4405)
n <- 350; x <- rnorm(n); w <- rnorm(n)
m <- 0.4*x+0.2*w+0.3*x*w+rnorm(n); y <- 0.4*m+0.2*x+0.2*w+0.1*x*w+rnorm(n)
d <- data.frame(x,w,m,y)
estimate <- function(data) { a <- coef(lm(m~x*w,data))["x:w"]; b <- coef(lm(y~x*w+m,data)); c(indirect=unname(a*b["m"]),direct_interaction=unname(b["x:w"])) }
point <- estimate(d); boot <- replicate(300,estimate(d[sample.int(n,n,replace=TRUE),])); ci <- quantile(boot["indirect",],c(0.025,0.975))
print(summary(lm(m~x*w,d))); print(summary(lm(y~x*w+m,d))); print(point); print(ci)
finish(c(indirect=unname(point["indirect"]),direct_interaction=unname(point["direct_interaction"]),ci_lower=unname(ci[1]),ci_upper=unname(ci[2])))

