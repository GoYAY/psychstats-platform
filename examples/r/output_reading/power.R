source("_common.R")
plan <- power.t.test(delta=3,sd=8,power=0.80,sig.level=0.05,type="two.sample")
print(plan)
tab <- data.frame(delta=c(2,3,4))
tab$per_group <- sapply(tab$delta,function(d) ceiling(power.t.test(delta=d,sd=8,power=0.80)$n))
print(tab)
finish(c(per_group=ceiling(plan$n),recruit_per_group=ceiling(ceiling(plan$n)/0.85),power=plan$power),list(sensitivity=tab))

