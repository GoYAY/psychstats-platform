source("examples/r/analyses/_common.R")
d <- read_data("scale_items")
x <- scale(d[paste0("item_",1:12)])
s <- cov(x); p <- ncol(s)
# Three correlated factors, each measured by four assigned items; all cross-loadings fixed to zero.
loss <- function(theta) {
  load <- matrix(0,p,3)
  for (j in 1:3) load[((j-1)*4+1):(j*4),j] <- theta[((j-1)*4+1):(j*4)]
  phi <- diag(3); phi[lower.tri(phi)] <- tanh(theta[13:15]); phi[upper.tri(phi)] <- t(phi)[upper.tri(phi)]
  if (min(eigen(phi,symmetric=TRUE,only.values=TRUE)$values) <= 0) return(1e9)
  sigma <- load %*% phi %*% t(load) + diag(exp(theta[16:27]),p)
  det <- determinant(sigma,logarithm=TRUE)
  if (det$sign <= 0) return(1e9)
  as.numeric(det$modulus) + sum(diag(solve(sigma,s)))
}
fit <- optim(c(rep(.7,12),rep(.2,3),rep(log(.5),12)),loss,method="BFGS",control=list(maxit=3000,reltol=1e-9))
emit(c(converged=as.integer(fit$convergence==0), mean_loading=mean(abs(fit$par[1:12])), discrepancy=fit$value))
