import { AuthPageShell } from "../features/auth/AuthPageShell";
import { Link } from "react-router-dom";

export default function VerifyNoticePage() {
  return (
    <AuthPageShell
      title="Check your email."
      subtitle="We've sent a verification link to your inbox. You need to click it before you can join the club."
      mode="login"
    >
      <div className="text-center pt-4">
        <p className="font-bold text-black mb-6">
          Didn't receive anything? Check your spam folder or wait a few minutes.
        </p>
        <Link
          to="/signup"
          className="inline-block w-full rounded-2xl border-4 border-black bg-primary px-5 py-4 font-black text-black shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all"
        >
          Back to Signup
        </Link>
      </div>
    </AuthPageShell>
  );
}
