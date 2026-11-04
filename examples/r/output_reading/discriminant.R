source("_common.R")
set.seed(4201)
group <- factor(rep(c("A","B","C"),each=70))
d <- data.frame(group,x1=rnorm(210,rep(c(-1,0,1),each=70),1),x2=rnorm(210,rep(c(0,1,-1),each=70),1))
lda <- MASS::lda(group~x1+x2,d,CV=TRUE); qda <- MASS::qda(group~x1+x2,d,CV=TRUE)
tab <- table(truth=group,predicted=lda$class); print(tab); print(table(truth=group,predicted=qda$class))
finish(c(lda_accuracy=mean(lda$class==group),qda_accuracy=mean(qda$class==group),mean_posterior=mean(apply(lda$posterior,1,max))),list(confusion=as.data.frame(tab)))

