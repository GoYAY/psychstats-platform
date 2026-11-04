# Append-only reporting extraction. Original analysis.R and result.json stay intact.
coefficient_table <- function(model, outcome) {
  s <- coef(summary(model)); ci <- if(inherits(model,'glm')) confint.default(model) else confint(model)
  data.frame(outcome=outcome,term=rownames(s),estimate=s[,1],se=s[,2],
             statistic=s[,3],df=if(inherits(model,'glm')) NA else df.residual(model),p=s[,4],
             ci_lower=ci[,1],ci_upper=ci[,2],row.names=NULL)
}
paper_tables <- list(); prediction_grid <- list()
SEM_CASES <- c('cfa','sem','path','mediation','latent-mediation','latent-interaction',
  'feedback','growth','invariance','multigroup','reliability-omega')
if (CASE_ID %in% c('conditional-mediation','mediated-interaction')) {
  model_m <- lm(m ~ x*w,data=d)
  model_y <- if (CASE_ID=='conditional-mediation') lm(y ~ x+m+w,data=d) else lm(y ~ x*w+m,data=d)
  paper_tables$path_coefficients <- rbind(coefficient_table(model_m,'m'),coefficient_table(model_y,'y'))
  paper_tables$model_summary <- data.frame(outcome=c('m','y'),n=c(nobs(model_m),nobs(model_y)),
      r_squared=c(summary(model_m)$r.squared,summary(model_y)$r.squared),
      adjusted_r_squared=c(summary(model_m)$adj.r.squared,summary(model_y)$adj.r.squared))
  if (CASE_ID=='mediated-interaction') {
    direct_row <- coefficient_table(model_y,'y')
    direct_row <- direct_row[direct_row$term=='x:w',]
    paper_tables$interaction_effects <- data.frame(effect=c('间接交互效应 a3×b','直接交互效应'),
      estimate=unname(point[c('indirect','direct_interaction')]),
      se=c(sd(boot['indirect',]),direct_row$se),p=c(NA,direct_row$p),
      ci_lower=c(ci[1],direct_row$ci_lower),ci_upper=c(ci[2],direct_row$ci_upper))
  }
} else if (CASE_ID=='moderation') {
  paper_tables$path_coefficients <- coefficient_table(fit,'well_being')
  paper_tables$model_summary <- data.frame(n=nobs(fit),r_squared=summary(fit)$r.squared,
    adjusted_r_squared=summary(fit)$adj.r.squared)
  wvalues <- c(-sd(d$w),0,sd(d$w))
  prediction_grid <- do.call(rbind,lapply(seq_along(wvalues),function(i) {
    grid <- data.frame(x=seq(min(d$x),max(d$x),length.out=41),w=wvalues[i])
    pr <- predict(fit,grid,interval='confidence',level=0.95)
    data.frame(group=c('低支持（−1 SD）','平均支持','高支持（+1 SD）')[i],
      x=grid$x,w=grid$w,estimate=pr[,'fit'],ci_lower=pr[,'lwr'],ci_upper=pr[,'upr'])
  }))
} else if (CASE_ID %in% c('linear','linear-simple','logistic','ancova','selection')) {
  reporting_fit <- if (CASE_ID=='selection') selected else fit
  paper_tables$reported_coefficients <- coefficient_table(reporting_fit,as.character(formula(reporting_fit)[[2]]))
  if (inherits(reporting_fit,'glm')) {
    z <- paper_tables$reported_coefficients
    paper_tables$odds_ratios <- data.frame(term=z$term,OR=exp(z$estimate),
      ci_lower=exp(z$ci_lower),ci_upper=exp(z$ci_upper),p=z$p)
    paper_tables$model_summary <- data.frame(n=nobs(reporting_fit),AIC=AIC(reporting_fit))
  } else {
    paper_tables$model_summary <- data.frame(n=nobs(reporting_fit),r_squared=summary(reporting_fit)$r.squared,
      adjusted_r_squared=summary(reporting_fit)$adj.r.squared)
  }
} else if (CASE_ID %in% c('hierarchical','kmeans','lpa')) {
  if (CASE_ID=='lpa') {
    centres <- t(fit$parameters$mean)
    norm_centres <- sweep(sweep(centres,2,colMeans(d),'-'),2,apply(d,2,sd),'/')
    paper_tables$standardized_profiles <- data.frame(class=seq_len(nrow(norm_centres)),norm_centres)
  } else {
    membership <- if(CASE_ID=='hierarchical') cluster else fit$cluster
    paper_tables$standardized_profiles <- aggregate(as.data.frame(scale(d)),list(cluster=membership),mean)
  }
  paper_tables$model_summary <- data.frame(n=nrow(d))
} else if (CASE_ID=='t-tests') {
  pooled <- sqrt(((length(a)-1)*var(a)+(length(b)-1)*var(b))/(length(a)+length(b)-2))
  J <- 1-3/(4*(length(a)+length(b)-2)-1)
  g <- J*(mean(a)-mean(b))/pooled
  set.seed(4701)
  gb <- replicate(1000,{
    aa <- sample(a,replace=TRUE);bb <- sample(b,replace=TRUE)
    J*(mean(aa)-mean(bb))/sqrt(((length(aa)-1)*var(aa)+(length(bb)-1)*var(bb))/(length(aa)+length(bb)-2))
  })
  interval_g <- quantile(gb,c(.025,.975))
  paper_tables$group_descriptives <- data.frame(group=c('retrieval','control'),
    n=c(length(a),length(b)),mean=c(mean(a),mean(b)),sd=c(sd(a),sd(b)))
  paper_tables$standardized_effects <- data.frame(effect='独立组 Hedges g（合并 SD）',estimate=g,
    ci_lower=interval_g[1],ci_upper=interval_g[2])
  change <- d$post_score-d$pre_score
  paper_tables$paired_change <- data.frame(n=length(change),difference=mean(change),
    se=sd(change)/sqrt(length(change)),t=unname(paired$statistic),df=unname(paired$parameter),
    p=paired$p.value,ci_lower=paired$conf.int[1],ci_upper=paired$conf.int[2],d_z=mean(change)/sd(change))
} else if (CASE_ID=='t-single') {
  observed_d <- (mean(x)-7)/sd(x)
  set.seed(4702); db <- replicate(1000,{xx<-sample(x,replace=TRUE);(mean(xx)-7)/sd(xx)})
  ci_d <- quantile(db,c(.025,.975))
  paper_tables$standardized_effects <- data.frame(effect='单样本 Cohen d（参照均值 7）',
    estimate=observed_d,ci_lower=ci_d[1],ci_upper=ci_d[2],n=length(x))
} else if (CASE_ID %in% SEM_CASES) {
  reporting_fit <- if(CASE_ID=='invariance') scalar else if(CASE_ID=='multigroup') free else fit
  counts <- lavaan::lavInspect(reporting_fit,'nobs')
  paper_tables$model_summary <- data.frame(group=seq_along(counts),n=as.numeric(counts))
  explained <- lavaan::lavInspect(reporting_fit,'rsquare')
  if(!is.list(explained)) explained <- list(explained)
  paper_tables$explained_variance <- do.call(rbind,lapply(seq_along(explained),function(i) {
    data.frame(group=i,outcome=names(explained[[i]]),r_squared=unname(explained[[i]]))
  }))
}
interval_method <- if(CASE_ID %in% c('t-tests','t-single')) '标准化效应量：1000 次教学 Bootstrap 百分位 95% CI' else
  if(CASE_ID=='logistic') 'log-odds / OR：Wald 95% CI' else
  if(CASE_ID %in% c('hierarchical','kmeans','lpa')) '画像：全体样本均值及 SD 标准化，未计算置信区间' else
  if(CASE_ID %in% SEM_CASES) 'SEM：参数区间沿用原模型估计器及算法；样本数与 R² 从实际模型对象提取' else
  '回归系数：t 分布 95% CI；间接效应：300 次教学 Bootstrap 百分位区间（如适用）'
jsonlite::write_json(list(tables=paper_tables,prediction_grid=prediction_grid,
  interval_method=interval_method,
  session_info=paste(capture.output(sessionInfo()),collapse='\n')),
  'paper-result.json',auto_unbox=TRUE,digits=16,pretty=TRUE,na='null')
