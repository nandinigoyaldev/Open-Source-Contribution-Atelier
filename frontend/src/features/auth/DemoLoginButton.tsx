import { useAppDispatch } from "../../store/hooks";
import { setDemoUser } from "../../features/auth/authSlice";
import { isDemoLoginEnabled } from "../../lib/googleOAuth";
import { useNavigate } from "react-router-dom";

type DemoLoginButtonProps = {
  label?: string;
  className?: string;
};

/**
 * Explicit opt-in demo session — only rendered when demo login is enabled.
 * Must never be triggered from Google OAuth failure handlers.
 */
export function DemoLoginButton({
  label = "🚀 Demo Mode (explicit local demo)",
  className = "w-full rounded-xl border-2 border-black bg-green-200 px-4 py-3.5 font-black text-black text-sm shadow-card-sm hover:-translate-y-0.5 transition-all cursor-pointer uppercase",
}: DemoLoginButtonProps) {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  if (!isDemoLoginEnabled()) return null;

  return (
    <button
      type="button"
      data-testid="demo-login-button"
      onClick={() => {
        dispatch(setDemoUser());
        navigate("/dashboard");
      }}
      className={className}
      title="Starts a local demo session without OAuth. Disabled in production unless VITE_ALLOW_DEMO_LOGIN=true."
    >
      {label}
    </button>
  );
}
