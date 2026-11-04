source("_common.R")
set.seed(4502)
n <- 300; z <- rnorm(n); x <- 0.4*z+rnorm(n); y <- 0.5*x+0.3*z+rnorm(n)
d <- data.frame(x,z,y); d$x[runif(n)<plogis(-1+0.6*z)] <- NA
observed <- !is.na(d$x); imputation <- lm(x~y+z,d,subset=observed)
X <- model.matrix(imputation); inv <- solve(crossprod(X)); df <- df.residual(imputation)
allX <- model.matrix(~y+z,d); m <- 20
fits <- lapply(seq_len(m),function(i) {
  sigma2 <- sum(resid(imputation)^2)/rchisq(1,df)
  beta <- drop(coef(imputation)+t(chol(sigma2*inv))%*%rnorm(ncol(X)))
  complete <- d; complete$x[!observed] <- drop(allX[!observed,,drop=FALSE]%*%beta)+rnorm(sum(!observed),sd=sqrt(sigma2))
  lm(y~x+z,complete)
})
Q <- sapply(fits,function(f)coef(f)["x"]); U <- sapply(fits,function(f)vcov(f)["x","x"])
q <- mean(Q); u <- mean(U); b <- var(Q); total <- u+(1+1/m)*b
lambda <- (1+1/m)*b/total; old_df <- (m-1)/lambda^2; dfcom <- n-3
observed_df <- (dfcom+1)/(dfcom+3)*dfcom*(1-lambda); pooled_df <- 1/(1/old_df+1/observed_df)
ci <- q+c(-1,1)*qt(0.975,pooled_df)*sqrt(total)
fiml <- lavaan::sem("y ~ x+z",d,missing="ML",fixed.x=FALSE,meanstructure=TRUE); check_sem(fiml)
pe <- lavaan::parameterEstimates(fiml); target <- pe[pe$lhs=="y"&pe$rhs=="x"&pe$op=="~",]
print(data.frame(imputation=1:m,estimate=Q,variance=U)); print(c(pooled=q,se=sqrt(total),df=pooled_df)); print(summary(fiml))
finish(c(pooled=q,se=sqrt(total),df=pooled_df,ci_lower=ci[1],ci_upper=ci[2],fiml=target$est,missing_proportion=mean(!observed)),list(imputations=data.frame(imputation=1:m,estimate=Q,variance=U),fiml_parameters=pe))

