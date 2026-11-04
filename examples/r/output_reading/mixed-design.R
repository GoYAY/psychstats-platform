source("_common.R")
set.seed(4116)
n <- 72
group <- factor(rep(c("control","practice"),each=36))
id <- factor(rep(seq_len(n),each=3))
time <- factor(rep(c("pre","post","followup"),n),levels=c("pre","post","followup"))
person <- rnorm(n,0,6)
long_group <- rep(group,each=3)
time_effect <- ifelse(long_group=="practice",rep(c(0,6,7),n),rep(c(0,2,2),n))
score <- 60+rep(person,each=3)+2*(long_group=="practice")+time_effect+rnorm(n*3,sd=rep(c(4,6,9),n))
d <- data.frame(id,group=long_group,time,score)
fit <- aov(score~group*time+Error(id/time),d)
output <- summary(fit); print(output)
between <- output[["Error: id"]][[1]]
within <- output[["Error: id:time"]][[1]]
wide <- matrix(score,ncol=3,byrow=TRUE)
mlm <- lm(wide~group)
S <- crossprod(residuals(mlm))/df.residual(mlm)
H <- diag(3)-matrix(1/3,3,3); A <- H%*%S%*%H
epsilon <- sum(diag(A))^2/(2*sum(A*A))
sphere <- mauchly.test(mlm,X=~1); print(sphere)
effects <- data.frame(effect=c("group","time","group:time"),
 F=c(between["group","F value"],within["time","F value"],within["group:time","F value"]),
 df1=c(between["group","Df"],within["time","Df"],within["group:time","Df"]),
 df2=c(between["Residuals","Df"],within["Residuals","Df"],within["Residuals","Df"]))
effects$epsilon <- c(1,epsilon,epsilon)
effects$reference_df1 <- effects$df1*effects$epsilon
effects$reference_df2 <- effects$df2*effects$epsilon
effects$p_reference <- pf(effects$F,effects$reference_df1,effects$reference_df2,lower.tail=FALSE)
print(effects)
change <- wide[,3]-wide[,1]
z <- t.test(change[group=="practice"],change[group=="control"])
change_table <- data.frame(comparison="practice minus control: followup-pre",
 difference=unname(z$estimate[1]-z$estimate[2]),df=unname(z$parameter),
 ci_lower=z$conf.int[1],ci_upper=z$conf.int[2],p=z$p.value)
print(change_table)
finish(c(people=n,observations=nrow(d),group_F=effects$F[1],group_p=effects$p_reference[1],
 interaction_F=effects$F[3],interaction_gg_p=effects$p_reference[3],gg_epsilon=epsilon,
 interaction_df1=effects$reference_df1[3],interaction_df2=effects$reference_df2[3],
 change_difference=change_table$difference,change_ci_lower=change_table$ci_lower,change_ci_upper=change_table$ci_upper),
 list(mixed_effects=effects,change_comparison=change_table))
