source("_common.R")
d <- read.csv("learning_experiment.csv")
a <- d$gain[d$condition=="retrieval"]; b <- d$gain[d$condition=="control"]
fit <- t.test(a,b)
paired <- t.test(d$post_score,d$pre_score,paired=TRUE)
print(fit); print(paired)
finish(c(difference=mean(a)-mean(b),ci_lower=fit$conf.int[1],ci_upper=fit$conf.int[2],t=unname(fit$statistic),df=unname(fit$parameter),p=fit$p.value))
