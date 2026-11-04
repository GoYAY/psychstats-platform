source("_common.R")
set.seed(4603); x <- rnorm(65,6.8,1.1); fit <- t.test(x,mu=7); print(fit)
finish(c(mean=mean(x),t=unname(fit$statistic),df=unname(fit$parameter),p=fit$p.value,ci_lower=fit$conf.int[1],ci_upper=fit$conf.int[2]))

