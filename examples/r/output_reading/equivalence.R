source("_common.R")
set.seed(4102)
x <- rnorm(90,70,8); y <- rnorm(90,70.2,8)
lower <- t.test(x,y,mu=-3,alternative="greater")
upper <- t.test(x,y,mu=3,alternative="less")
interval <- t.test(x,y,conf.level=0.90)
print(lower); print(upper); print(interval)
finish(c(difference=mean(x)-mean(y),lower_p=lower$p.value,upper_p=upper$p.value,tost_p=max(lower$p.value,upper$p.value),ci_lower=interval$conf.int[1],ci_upper=interval$conf.int[2],margin=3))

