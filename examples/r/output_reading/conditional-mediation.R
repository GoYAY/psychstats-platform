source("_common.R")
set.seed(4404)
n <- 350; x <- rnorm(n); w <- rnorm(n); w <- w-mean(w)
m <- 0.4*x+0.2*w+0.25*x*w+rnorm(n); y <- 0.5*m+0.2*x+0.1*w+rnorm(n)
d <- data.frame(x,w,m,y)
estimate <- function(data) { a <- coef(lm(m~x*w,data)); b <- coef(lm(y~x+m+w,data))["m"]; c(index=unname(a["x:w"]*b),at_zero=unname(a["x"]*b),at_low=unname((a["x"]-a["x:w"])*b),at_high=unname((a["x"]+a["x:w"])*b)) }
point <- estimate(d); boot <- replicate(300,estimate(d[sample.int(n,n,replace=TRUE),]))
interval <- apply(boot,1,quantile,c(0.025,0.975))
print(summary(lm(m~x*w,d))); print(summary(lm(y~x+m+w,d)))
tab <- data.frame(effect=names(point),estimate=as.numeric(point),ci_lower=interval[1,],ci_upper=interval[2,]); print(tab)
finish(c(index=unname(point["index"]),ci_lower=interval[1,"index"],ci_upper=interval[2,"index"],at_zero=unname(point["at_zero"])),list(conditional_effects=tab))

