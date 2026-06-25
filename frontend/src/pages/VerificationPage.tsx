import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

export function VerificationPage() {
  const { token } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    const verifyUser = async () => {
      try {
        // Uses Vercel environment variable in production, falls back to local dev server
        const baseUrl =
          import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";
        const response = await fetch(`${baseUrl}/auth/verify/${token}/`, {
          method: "GET",
        });

        if (response.ok) {
          alert("Verification successful!");
          navigate("/login"); // Adjust to your login route
        } else {
          alert("Verification failed.");
        }
      } catch (error) {
        console.error("Error verifying:", error);
      }
    };

    if (token) verifyUser();
  }, [token, navigate]);

  return <div>Verifying your account, please wait...</div>;
}
