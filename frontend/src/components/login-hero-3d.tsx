"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line } from "@react-three/drei";
import type { Group, Mesh } from "three";
import { useReducedMotion } from "@/lib/use-reduced-motion";

/**
 * "Matching constellation" — a central core (the candidate / CV) with job
 * opportunities orbiting and tethered to it by light-lines. Visualizes the
 * project's core idea: continuously matching you to the right roles.
 */

interface NodeSpec {
  radius: number;
  speed: number;
  tiltX: number;
  tiltZ: number;
  phase: number;
  scale: number;
  color: string;
}

const COLORS = ["#bff747", "#5eead4", "#e9ecef", "#bff747", "#a3e635"];

function OrbitNode({ radius, speed, tiltX, tiltZ, phase, scale, color }: NodeSpec) {
  const ref = useRef<Group>(null);
  useFrame((_, d) => {
    if (ref.current) ref.current.rotation.y += d * speed;
  });
  return (
    <group rotation={[tiltX, phase, tiltZ]}>
      <group ref={ref}>
        <Line
          points={[
            [0, 0, 0],
            [radius, 0, 0],
          ]}
          color="#bff747"
          lineWidth={1}
          transparent
          opacity={0.22}
        />
        <mesh position={[radius, 0, 0]} scale={scale}>
          <sphereGeometry args={[0.09, 18, 18]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} />
        </mesh>
      </group>
    </group>
  );
}

function Core() {
  const ref = useRef<Mesh>(null);
  useFrame((_, d) => {
    if (ref.current) {
      ref.current.rotation.y += d * 0.25;
      ref.current.rotation.x += d * 0.1;
    }
  });
  return (
    <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.6}>
      <mesh ref={ref}>
        <icosahedronGeometry args={[0.55, 1]} />
        <meshStandardMaterial
          color="#bff747"
          emissive="#bff747"
          emissiveIntensity={0.5}
          wireframe
        />
      </mesh>
    </Float>
  );
}

export default function LoginHero3D() {
  const nodes = useMemo<NodeSpec[]>(() => {
    const rng = (a: number, b: number) => a + Math.random() * (b - a);
    return Array.from({ length: 11 }).map((_, i) => ({
      radius: rng(1.3, 2.5),
      speed: rng(0.12, 0.5) * (Math.random() > 0.5 ? 1 : -1),
      tiltX: rng(-1.2, 1.2),
      tiltZ: rng(-1.2, 1.2),
      phase: rng(0, Math.PI * 2),
      scale: rng(0.7, 1.5),
      color: COLORS[i % COLORS.length],
    }));
  }, []);

  const reduced = useReducedMotion();
  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 50 }}
      dpr={[1, 2]}
      frameloop={reduced ? "never" : "always"}
      gl={{ alpha: true }}
    >
      <ambientLight intensity={0.6} />
      <pointLight position={[5, 5, 5]} intensity={1.1} color="#bff747" />
      <pointLight position={[-5, -5, -5]} intensity={0.45} color="#5eead4" />
      <Core />
      {nodes.map((n, i) => (
        <OrbitNode key={i} {...n} />
      ))}
    </Canvas>
  );
}
