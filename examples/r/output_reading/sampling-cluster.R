source("_common.R")
set.seed(4608); Nc <- 40; nc <- 10; pupils <- 20
classmean <- rnorm(Nc,65,5); population <- matrix(rep(classmean,each=pupils)+rnorm(Nc*pupils,sd=8),nrow=Nc,byrow=TRUE)
selected <- sample.int(Nc,nc); means <- rowMeans(population[selected,,drop=FALSE]); estimate <- mean(means)
se <- sqrt((1-nc/Nc)*var(means)/nc); ci <- estimate+c(-1,1)*qt(0.975,nc-1)*se
print(c(sampled_classes=nc,student_records=nc*pupils,estimate=estimate,se=se)); print(ci)
finish(c(mean=estimate,se=se,ci_lower=ci[1],ci_upper=ci[2],classes=nc,records=nc*pupils))

