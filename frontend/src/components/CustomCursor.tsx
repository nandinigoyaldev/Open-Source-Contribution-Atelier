import { useEffect, useRef, useState } from "react";

const HOVER_TARGET_SELECTOR =
  'a, button, input, textarea, select, [role="button"], [data-cursor-hover], .cursor-pointer';

export function CustomCursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const [isTouchDevice, setIsTouchDevice] = useState(true);

  // Detect touch devices once, on mount
  useEffect(() => {
    const touch =
      window.matchMedia("(pointer: coarse)").matches ||
      "ontouchstart" in window;
    setIsTouchDevice(touch);
  }, []);

  useEffect(() => {
    if (isTouchDevice) return;

    document.body.classList.add("custom-cursor-active");

    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const ring = { x: mouse.x, y: mouse.y };
    let animationFrame: number;

    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      if (dotRef.current) {
        dotRef.current.style.transform = `translate3d(${mouse.x}px, ${mouse.y}px, 0) translate(-50%, -50%)`;
      }
    };

    const handleMouseOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest(HOVER_TARGET_SELECTOR)) {
        ringRef.current?.classList.add("custom-cursor-ring--hover");
      }
    };

    const handleMouseOut = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest(HOVER_TARGET_SELECTOR)) {
        ringRef.current?.classList.remove("custom-cursor-ring--hover");
      }
    };

    const handleMouseDown = () =>
      ringRef.current?.classList.add("custom-cursor-ring--click");
    const handleMouseUp = () =>
      ringRef.current?.classList.remove("custom-cursor-ring--click");

    // Ring follows mouse with a smooth "lag" (lerp)
    const animateRing = () => {
      ring.x += (mouse.x - ring.x) * 0.15;
      ring.y += (mouse.y - ring.y) * 0.15;
      if (ringRef.current) {
        ringRef.current.style.transform = `translate3d(${ring.x}px, ${ring.y}px, 0) translate(-50%, -50%)`;
      }
      animationFrame = requestAnimationFrame(animateRing);
    };

    window.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseover", handleMouseOver);
    document.addEventListener("mouseout", handleMouseOut);
    window.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);
    animationFrame = requestAnimationFrame(animateRing);

    return () => {
      document.body.classList.remove("custom-cursor-active");
      window.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseover", handleMouseOver);
      document.removeEventListener("mouseout", handleMouseOut);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
      cancelAnimationFrame(animationFrame);
    };
  }, [isTouchDevice]);

  // On touch devices, render nothing — keep native cursor/touch behavior
  if (isTouchDevice) return null;

  return (
    <>
      <div ref={dotRef} className="custom-cursor-dot" />
      <div ref={ringRef} className="custom-cursor-ring" />
    </>
  );
}

export default CustomCursor;
