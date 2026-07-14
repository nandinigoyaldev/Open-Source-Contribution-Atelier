/**
 * Certificate page with social sharing buttons.
 *
 * @file CertificatePage.tsx
 * @location frontend/src/pages/CertificatePage.tsx
 */

import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { CertificateShareButtons } from "../components/Certificate/CertificateShareButtons";
import toast from "react-hot-toast";

interface Certificate {
  id: string;
  user: string;
  username: string;
  course_name: string;
  issued_date: string;
  verification_hash: string;
  is_active: boolean;
}

export const CertificatePage: React.FC = () => {
  const { hash } = useParams<{ hash: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [certificate, setCertificate] = useState<Certificate | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCertificate = async () => {
      if (!hash) {
        setError("Certificate not found");
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`/api/progress/verify/${hash}/`);
        if (!response.ok) {
          throw new Error("Certificate not found");
        }
        const data = await response.json();
        setCertificate(data.certificate);
      } catch (err) {
        setError("Failed to load certificate");
        toast.error("Certificate not found");
      } finally {
        setIsLoading(false);
      }
    };

    fetchCertificate();
  }, [hash]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mb-4" />
          <p className="text-gray-400">Loading certificate...</p>
        </div>
      </div>
    );
  }

  if (error || !certificate) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center">
        <div className="text-center text-gray-400">
          <h2 className="text-2xl font-bold mb-2">❌ Certificate Not Found</h2>
          <p>
            The certificate you're looking for doesn't exist or has been
            revoked.
          </p>
          <button
            onClick={() => navigate("/")}
            className="mt-4 px-4 py-2 bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  // Build certificate URL for sharing
  const certificateUrl = `${window.location.origin}/certificate/verify/${certificate.verification_hash}`;

  return (
    <div className="min-h-screen bg-dark-900 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Certificate Card */}
        <div className="bg-dark-800 rounded-xl border border-dark-700 p-8 shadow-xl">
          <div className="text-center">
            <div className="text-5xl mb-4">🏆</div>
            <h1 className="text-3xl font-bold text-white mb-2">
              Certificate of Completion
            </h1>
            <p className="text-gray-400 mb-6">This certifies that</p>
            <p className="text-2xl font-bold text-blue-400 mb-2">
              {certificate.username || "User"}
            </p>
            <p className="text-gray-400 mb-6">
              has successfully completed the course
            </p>
            <p className="text-xl font-semibold text-white mb-6">
              {certificate.course_name}
            </p>
            <p className="text-gray-500 text-sm">
              Issued on {new Date(certificate.issued_date).toLocaleDateString()}
            </p>
            <p className="text-gray-600 text-xs mt-2">
              Verification: {certificate.verification_hash}
            </p>

            <div className="mt-8 pt-6 border-t border-dark-700">
              <p className="text-gray-400 text-sm mb-4">
                Share your achievement on social media!
              </p>

              {/* ✅ Share Buttons */}
              <CertificateShareButtons
                certificateUrl={certificateUrl}
                certificateName={certificate.course_name}
                userName={certificate.username || user?.username || "User"}
                className="justify-center"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CertificatePage;
