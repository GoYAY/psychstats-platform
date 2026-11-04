source("_common.R")
set.seed(4108)
a <- rlnorm(55,2,0.8); b <- rlnorm(60,2.2,0.8); c <- rlnorm(50,2.1,1)
fit <- wilcox.test(a,b,exact=FALSE,conf.int=TRUE); print(fit)
kw <- kruskal.test(list(a,b,c)); print(kw)
before <- rlnorm(40,2,0.5); after <- before-rnorm(40,1,1)
paired <- wilcox.test(before,after,paired=TRUE,exact=FALSE); print(paired)
finish(c(W=unname(fit$statistic),p=fit$p.value,shift=unname(fit$estimate),kw_p=kw$p.value,paired_p=paired$p.value))

