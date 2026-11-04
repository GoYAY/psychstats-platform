source("_common.R")
set.seed(4604); n <- 100; before <- rbinom(n,1,0.3); after <- rbinom(n,1,0.45)
tab <- table(before=factor(before,levels=0:1),after=factor(after,levels=0:1)); print(tab)
fit <- mcnemar.test(tab,correct=TRUE); discordant <- tab[1,2]+tab[2,1]; exact <- binom.test(tab[1,2],discordant,p=0.5)
print(fit); print(exact)
finish(c(p=fit$p.value,exact_p=exact$p.value,discordant=discordant,difference=mean(after)-mean(before)),list(paired_counts=as.data.frame(tab)))

