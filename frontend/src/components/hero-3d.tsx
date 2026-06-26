"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Icosahedron, MeshDistortMaterial } from "@react-three/drei";
import type { Mesh } from "three";
import { useReducedMotion } from "@/lib/use-reduced-motion";

function Blob() {
  const ref = useRef<Mesh>(null);
  useFrame((state, delta) => {
    const m = ref.current;
    if (!m) return;
    m.rotation.y += delta * 0.18;
    m.rotation.x += delta * 0.08;
    // Gentle parallax toward the pointer.
    m.position.x = state.pointer.x * 0.15;
    m.position.y = state.pointer.y * 0.15;
  });

  return (
    <Float speed={1.4} rotationIntensity={0.6} floatIntensity={0.8}>
      <Icosahedron ref={ref} args={[1.5, 8]}>
        <MeshDistortMaterial
          color="#bff747"
          emissive="#9ade1f"
          emissiveIntensity={0.35}
          roughness={0.35}
          metalness={0.15}
          distort={0.4}
          speed={1.8}
          wireframe
        />
      </Icosahedron>
    </Float>
  );
}

export default function Hero3D() {
  const reduced = useReducedMotion();
  return (
    <Canvas
      camera={{ position: [0, 0, 4.2], fov: 45 }}
      dpr={[1, 2]}
      frameloop={reduced ? "never" : "always"}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[4, 4, 5]} intensity={1.2} color="#bff747" />
      <pointLight position={[-5, -3, -4]} intensity={0.6} color="#5eead4" />
      <Blob />
    </Canvas>
  );
}
