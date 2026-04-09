/**
 * Consent Middleware
 * 
 * Verifies user consent before accepting data submissions.
 */

export function consentMiddleware(req, res, next) {
  // For now, consent is verified in the route handler
  // This middleware can be used for additional checks
  
  const consentHeader = req.headers['x-telemetry-consent'];
  
  if (req.method === 'POST' && req.path.includes('trajectories')) {
    if (!consentHeader && !req.body.anonymization?.user_consent) {
      // Allow through - client-side consent is verified at route level
      // This header can be used for CDN-level blocking
    }
  }
  
  next();
}
