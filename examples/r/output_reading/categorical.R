source("_common.R")
set.seed(4107)
d <- data.frame(group=rep(c("no","yes"),each=90),help=c(rbinom(90,1,0.30),rbinom(90,1,0.45)))
tab <- table(d$group,d$help); print(tab)
fit <- chisq.test(tab,correct=FALSE); print(fit); print(fit$expected)
fisher <- fisher.test(tab); print(fisher)
finish(c(chi_squared=unname(fit$statistic),df=unname(fit$parameter),p=fit$p.value,min_expected=min(fit$expected),odds_ratio=unname(fisher$estimate),fisher_p=fisher$p.value),list(counts=as.data.frame(tab),expected=as.data.frame(as.table(fit$expected))))

