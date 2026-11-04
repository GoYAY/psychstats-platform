source("_common.R")
d <- latent_teaching(400,4607)[1:3]
fit <- lavaan::cfa("f =~ x1+x2+x3",d); check_sem(fit)
pe <- lavaan::parameterEstimates(fit); lambda <- pe$est[pe$op=="=~"]; phi <- pe$est[pe$lhs=="f"&pe$rhs=="f"&pe$op=="~~"]; theta <- pe$est[pe$op=="~~"&pe$lhs==pe$rhs&pe$lhs!="f"]
omega <- sum(lambda)^2*phi/(sum(lambda)^2*phi+sum(theta))
alpha <- psych::alpha(d,check.keys=FALSE)$total$raw_alpha
print(summary(fit)); print(c(omega_total=omega,alpha=alpha))
finish(c(omega=omega,alpha=alpha,n=nrow(d)),list(parameters=pe))

