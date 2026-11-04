source("_common.R")
set.seed(4605)
d <- expand.grid(training=factor(c("A","B")),feedback=factor(c("no","yes")),person=1:40)
d$score <- 60+3*(d$training=="B")+2*(d$feedback=="yes")+4*(d$training=="B"&d$feedback=="yes")+rnorm(nrow(d),0,7)
fit <- aov(score~training*feedback,d); tab <- summary(fit)[[1]]; print(summary(fit))
block <- expand.grid(block=factor(1:8),condition=factor(c("A","B","C"))); block$score <- 50+as.numeric(block$block)+c(0,3,5)[as.numeric(block$condition)]+rnorm(nrow(block),0,2)
blocked <- aov(score~block+condition,block); bt <- summary(blocked)[[1]]; print(summary(blocked))
finish(c(interaction_F=tab[3,"F value"],df1=tab[3,"Df"],df2=tab[4,"Df"],interaction_p=tab[3,"Pr(>F)"],block_p=bt[2,"Pr(>F)"]),list(factorial=data.frame(term=rownames(tab),tab),blocked=data.frame(term=rownames(bt),bt)))

