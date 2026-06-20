import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

export function VerificationPage() {
  const { token } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    const verifyUser = async () => {
      try {
        // Adjust this URL if your backend is on a different port
        const response = await fetch(`http://127.0.0.1:8000/api/auth/verify/${token}/`, {
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