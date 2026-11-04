source("_common.R")
set.seed(4106)
n <- 150; group <- factor(rep(c("control","practice","combined"),each=50)); baseline <- rnorm(n)
e <- matrix(rnorm(n*2),n); memory <- 60+3*as.numeric(group)+2*baseline+5*e[,1]
attention <- 40+2*as.numeric(group)+baseline+3*e[,1]+4*e[,2]
d <- data.frame(group,baseline,memory,attention)
fit <- manova(cbind(memory,attention)~group,d); tab <- summary(fit,test="Pillai")$stats; print(summary(fit,test="Pillai"))
adjusted <- manova(cbind(memory,attention)~baseline+group,d); adjusted_tab <- summary(adjusted,test="Pillai")$stats; print(summary(adjusted,test="Pillai"))
outcomes <- c("memory","attention")
univariate <- list(); comparisons <- list(); coefficients <- list()
for (outcome in outcomes) {
 fm <- lm(reformulate(c("baseline","group"),outcome),d)
 test <- anova(update(fm,~baseline),fm)
 univariate[[outcome]] <- data.frame(outcome=outcome,F=test$F[2],df1=test$Df[2],df2=df.residual(fm),p=test$"Pr(>F)"[2])
 newdata <- data.frame(baseline=mean(d$baseline),group=factor(levels(d$group),levels=levels(d$group)))
 X <- model.matrix(delete.response(terms(fm)),newdata)
 pairs <- combn(seq_len(nrow(X)),2)
 comparisons[[outcome]] <- do.call(rbind,lapply(seq_len(ncol(pairs)),function(j){
  a<-pairs[1,j]; b<-pairs[2,j]; C<-X[b,]-X[a,]
  estimate<-sum(C*coef(fm)); se<-sqrt(drop(C%*%vcov(fm)%*%C)); df<-df.residual(fm); critical<-qt(0.975,df)
  data.frame(outcome=outcome,comparison=paste(levels(d$group)[b],"minus",levels(d$group)[a]),baseline=mean(d$baseline),difference=estimate,se=se,df=df,ci_lower=estimate-critical*se,ci_upper=estimate+critical*se,p=2*pt(-abs(estimate/se),df))
 }))
 z <- coef(summary(fm)); coefficients[[outcome]]<-data.frame(outcome=outcome,term=rownames(z),z,check.names=FALSE)
}
univariate <- do.call(rbind,univariate); comparisons <- do.call(rbind,comparisons)
adjusted_pvalues <- p.adjust(c(univariate$p,comparisons$p),method="holm")
univariate$p_holm <- adjusted_pvalues[seq_len(nrow(univariate))]
comparisons$p_holm <- adjusted_pvalues[nrow(univariate)+seq_len(nrow(comparisons))]
print(univariate); print(comparisons)
finish(c(pillai=tab["group","Pillai"],F=tab["group","approx F"],df1=tab["group","num Df"],df2=tab["group","den Df"],p=tab["group","Pr(>F)"],adjusted_p=adjusted_tab["group","Pr(>F)"],adjusted_pillai=adjusted_tab["group","Pillai"],adjusted_F=adjusted_tab["group","approx F"],adjusted_df1=adjusted_tab["group","num Df"],adjusted_df2=adjusted_tab["group","den Df"]),list(multivariate=data.frame(term=rownames(adjusted_tab),adjusted_tab,check.names=FALSE),univariate_followup=univariate,adjusted_pairwise_comparisons=comparisons,coefficients=do.call(rbind,coefficients)))
