source("_common.R")
set.seed(4105)
id <- factor(rep(seq_len(45),each=3)); time <- factor(rep(c("pre","post","followup"),45),levels=c("pre","post","followup"))
person <- rnorm(45,0,6); score <- 60+rep(person,each=3)+rep(c(0,5,4),45)+rnorm(135,0,4)
d <- data.frame(id,time,score)
fit <- aov(score~time+Error(id/time),d); output <- summary(fit); print(output)
tab <- output[["Error: id:time"]][[1]]
wide <- matrix(d$score,ncol=3,byrow=TRUE)
mlm <- lm(wide~1)
sphere <- mauchly.test(mlm,X=~1); print(sphere)
corrections <- anova(mlm,update(mlm,~0),X=~1,test="Spherical"); print(corrections)
H <- diag(3)-matrix(1/3,3,3); S <- cov(residuals(mlm)); A <- H%*%S%*%H
epsilon <- sum(diag(A))^2/(2*sum(A*A))
gg_df1 <- epsilon*tab[1,"Df"]; gg_df2 <- epsilon*tab[2,"Df"]
stopifnot(abs(pf(tab[1,"F value"],gg_df1,gg_df2,lower.tail=FALSE)-corrections[2,"G-G Pr"])<1e-10)
pairs <- combn(1:3,2)
comparisons <- do.call(rbind,lapply(seq_len(ncol(pairs)),function(j){
 a<-pairs[1,j]; b<-pairs[2,j]; z<-t.test(wide[,b],wide[,a],paired=TRUE)
 data.frame(comparison=paste(levels(time)[b],"minus",levels(time)[a]),difference=unname(z$estimate),ci_lower=z$conf.int[1],ci_upper=z$conf.int[2],p=z$p.value)
}))
comparisons$p_holm <- p.adjust(comparisons$p,"holm"); print(comparisons)
finish(c(F=tab[1,"F value"],df1=tab[1,"Df"],df2=tab[2,"Df"],p=tab[1,"Pr(>F)"],people=45,observations=nrow(d),gg_epsilon=epsilon,gg_p=corrections[2,"G-G Pr"],gg_df1=gg_df1,gg_df2=gg_df2,mauchly_p=sphere$p.value),list(sphericity_corrections=data.frame(corrections,check.names=FALSE),paired_comparisons=comparisons))
