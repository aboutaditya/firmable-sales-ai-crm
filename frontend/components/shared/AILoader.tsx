"use client";

export default function AILoader({ message = "Generating..." }: { message?: string }) {
  return (
    <div className="ai-loader">
      <style jsx>{`
        .ai-loader {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          padding: 24px;
        }

        .loader-container {
          display: flex;
          gap: 8px;
          align-items: center;
          justify-content: center;
        }

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          animation: bounce 1.4s infinite ease-in-out;
        }

        .dot:nth-child(1) {
          animation-delay: -0.32s;
        }

        .dot:nth-child(2) {
          animation-delay: -0.16s;
        }

        @keyframes bounce {
          0%, 80%, 100% {
            transform: scale(0.8);
            opacity: 0.6;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }

        .loader-text {
          font-size: 14px;
          font-weight: 500;
          color: #667eea;
          letter-spacing: 0.5px;
        }

        .spark {
          position: absolute;
          width: 4px;
          height: 4px;
          background: #764ba2;
          border-radius: 50%;
          animation: sparkle 1.5s ease-in-out infinite;
        }

        .spark:nth-child(1) {
          animation-delay: 0s;
          top: -10px;
          left: 10px;
        }

        .spark:nth-child(2) {
          animation-delay: 0.3s;
          top: 5px;
          right: -8px;
        }

        .spark:nth-child(3) {
          animation-delay: 0.6s;
          bottom: 5px;
          left: -8px;
        }

        @keyframes sparkle {
          0%, 100% {
            opacity: 0;
            transform: scale(0);
          }
          50% {
            opacity: 1;
            transform: scale(1);
          }
        }

        .loader-wrapper {
          position: relative;
        }
      `}</style>

      <div className="loader-wrapper">
        <div className="loader-container">
          <div className="dot" />
          <div className="dot" />
          <div className="dot" />
        </div>
        <div className="spark" />
        <div className="spark" />
        <div className="spark" />
      </div>

      <p className="loader-text">{message}</p>
    </div>
  );
}
