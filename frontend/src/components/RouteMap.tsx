import React, { useEffect, useMemo, useRef } from 'react';
import { Station } from '../types';

interface RouteMapProps {
  stations: Station[];
  selectedStation: Station | null;
  onSelectStation: (station: Station) => void;
  onDeselect?: () => void;
  skippingStationIds?: string[];
}
interface StationPos {
  station: Station;
  x: number;
  y: number;
  labelPos: 'top' | 'bottom' | 'left' | 'right';
  globalIndex: number;
}
// ── Layout constants ──────────────────────────────────────────────────────────
const TOTAL_WIDTH = 1600;
const TOTAL_HEIGHT = 720;
const MIN_X = 50;
const MAX_X = 1550;
const Y1 = 55; // Row 1  : 소요산 → 녹천   (L→R)
const Y2 = 185; // Row 2  : 월계 → 신길     (R→L)
const Y_ENG = 248; // 영등포  (left connector)
const Y_SIN = 310; // 신도림  (left connector)
const Y3A = 372; // Row 3a : 구로 → 병점     (L→R)
const Y_SPUR_UP = Y3A - 76; // Spurs: Gwangmyeong, Seodongtan (Flipped UP)
const Y3B = 504; // Row 3b : 세마 → 신창     (R→L)
const Y4 = 634; // Row 4  : 구일 → 인천     (L→R)
// Junction station IDs — structural branch/corner nodes
// 1001000141=Guro, 1001080142=Gasan, 1001080144=Geumcheon-gu Office, 1001080157=Byeongjeom
const JUNCTION_IDS = new Set(['1001000141', '1001080142', '1001080144', '1001080157']);
// ── Layout computation ────────────────────────────────────────────────────────
function computeLayout(allStations: Station[]): {
  positions: StationPos[];
  totalHeight: number;
  totalWidth: number;
} {
  const positions: StationPos[] = [];
  const add = (
  idx: number,
  x: number,
  y: number,
  labelPos: 'top' | 'bottom' | 'left' | 'right') =>
  {
    if (idx < allStations.length && allStations[idx]) {
      positions.push({
        station: allStations[idx],
        x,
        y,
        labelPos,
        globalIndex: idx
      });
    }
  };
  // ── ROW 1: 연천(0) → 녹천(20), L→R, 21 stations ──
  const r1sp = (MAX_X - MIN_X) / 20;
  for (let i = 0; i <= 20; i++) {
    const x = MIN_X + i * r1sp;
    let lp: 'top' | 'bottom' | 'left' | 'right';
    if (i === 20)
      lp = 'top'; // Nokcheon
    else lp = i % 2 === 0 ? 'top' : 'bottom';
    add(i, x, Y1, lp);
  }
  // ── ROW 2: 월계(21) → 신길(41), R→L, 21 stations ──
  const r2sp = (MAX_X - MIN_X) / 20;
  for (let i = 0; i <= 20; i++) {
    const x = MAX_X - i * r2sp;
    let lp: 'top' | 'bottom' | 'left' | 'right';
    if (i === 0)
      lp = 'bottom'; // Wolgye
    else if (i === 20)
      lp = 'left'; // Singil
    else lp = i % 2 === 0 ? 'bottom' : 'top';
    add(21 + i, x, Y2, lp);
  }
  // ── LEFT CONNECTOR: 영등포(42), 신도림(43), 구로(44) ──
  add(42, MIN_X, Y_ENG, 'right');
  add(43, MIN_X, Y_SIN, 'right');
  add(44, MIN_X, Y3A, 'left'); // Guro
  // ── ROW 3a: 가산디지털단지(65) → 병점(81), L→R, 16 stations ──
  const r3aIndices = [
  65, 66, 67, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81];

  const r3asp = (MAX_X - MIN_X) / 16;
  r3aIndices.forEach((idx, i) => {
    const x = MIN_X + (i + 1) * r3asp;
    let lp: 'top' | 'bottom' | 'left' | 'right';
    // Force 'top' for junctions (spur/connector goes down)
    // 64 (Geumcheon-gu Office): branch goes UP, so label moves to bottom
    // 78 (Byeongjeom): moved to right (3 o'clock) for better visibility near spur
    if (idx === 62) lp = 'top';
    else if (idx === 64) lp = 'bottom';
    else if (idx === 78) lp = 'right';
    else lp = i % 2 === 0 ? 'bottom' : 'top';
    add(idx, x, Y3A, lp);
  });
  // ── 광명 SPUR (68): above 금천구청(67) ──
  const gumcheonEntry = positions.find((p) => p.globalIndex === 67);
  if (gumcheonEntry) add(68, gumcheonEntry.x, Y_SPUR_UP, 'top');

  // ── 서동탄 SPUR (82): directly above 병점(81) ──
  add(82, MAX_X, Y_SPUR_UP, 'top');

  // ── ROW 3b: 세마(83) → 신창(100), R→L, 18 stations ──
  const r3bEnd = 135;
  const r3bsp = (MAX_X - r3bEnd) / 17;
  for (let i = 0; i <= 17; i++) {
    const x = MAX_X - i * r3bsp;
    let lp: 'top' | 'bottom' | 'left' | 'right';
    if (i === 0)
      lp = 'bottom';
    else if (i === 17)
      lp = 'top';
    else lp = i % 2 === 0 ? 'bottom' : 'top';
    
    add(83 + i, x, Y3B, lp);
  }
  // ── ROW 4: 구일(45) → 인천(64), L→R, 20 stations ──
  const r4Start = 125;
  const r4sp = (MAX_X - r4Start) / 19;
  for (let i = 0; i <= 19; i++) {
    const x = r4Start + i * r4sp;
    const lp: 'top' | 'bottom' = i % 2 === 0 ? 'top' : 'bottom';
    add(45 + i, x, Y4, lp);
  }
  positions.sort((a, b) => a.globalIndex - b.globalIndex);
  return {
    positions,
    totalHeight: TOTAL_HEIGHT,
    totalWidth: TOTAL_WIDTH
  };
}
// ── Component ─────────────────────────────────────────────────────────────────
export const RouteMap: React.FC<RouteMapProps> = ({
  stations: allStations,
  selectedStation,
  onSelectStation,
  onDeselect,
  skippingStationIds = []
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { positions, totalHeight, totalWidth } = useMemo(
    () => computeLayout(allStations),
    [allStations]
  );
  useEffect(() => {
    if (selectedStation && scrollRef.current) {
      const el = scrollRef.current.querySelector(
        `[data-station-id="${selectedStation.id}"]`
      );
      if (el)
      el.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'nearest'
      });
    }
  }, [selectedStation]);
  // ── Path builder ─────────────────────────────────────────────────────────
  const buildPath = (): string => {
    if (positions.length === 0) return '';
    type PP = {
      x: number;
      y: number;
      isJunction?: boolean;
    };
    const seg = (pts: PP[]): string => {
      if (pts.length === 0) return '';
      let d = `M ${pts[0].x},${pts[0].y}`;
      const R = 22;
      for (let i = 1; i < pts.length; i++) {
        const prev = pts[i - 1];
        const curr = pts[i];
        const next = i < pts.length - 1 ? pts[i + 1] : null;
        // Junctions: path passes straight through (no smoothing)
        if (curr.isJunction) {
          d += ` L ${curr.x},${curr.y}`;
          continue;
        }
        if (next) {
          const dx1 = curr.x - prev.x,
            dy1 = curr.y - prev.y;
          const dx2 = next.x - curr.x,
            dy2 = next.y - curr.y;
          const isCorner =
          Math.abs(dx1) > 30 && Math.abs(dy2) > 30 ||
          Math.abs(dy1) > 30 && Math.abs(dx2) > 30;
          if (isCorner) {
            const l1 = Math.sqrt(dx1 * dx1 + dy1 * dy1);
            const l2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);
            const r = Math.min(R, l1 / 2, l2 / 2);
            const bx = curr.x - dx1 / l1 * r,
              by = curr.y - dy1 / l1 * r;
            const ax = curr.x + dx2 / l2 * r,
              ay = curr.y + dy2 / l2 * r;
            d += ` L ${bx},${by} Q ${curr.x},${curr.y} ${ax},${ay}`;
            continue;
          }
        }
        d += ` L ${curr.x},${curr.y}`;
      }
      return d;
    };
    const tp = (p: StationPos): PP => ({
      x: p.x,
      y: p.y,
      isJunction: JUNCTION_IDS.has(p.station.id)
    });
    // 1. Trunk: 연천(0) → 구로(44)
    let path = seg(positions.slice(0, 45).map(tp));
    const guro = positions[44];
    if (guro) {
      // 2. South branch: 구로 → 가산디지털단지 → … → 병점 → 세마 → … → 신창
      const southPts: PP[] = [tp(guro)];
      for (let i = 65; i <= 101; i++) {
        if (i === 68 || i === 82) continue; // skip spurs
        const p = positions.find((q: StationPos) => q.globalIndex === i);
        if (p) southPts.push(tp(p));
      }
      path += ' ' + seg(southPts);
      // 3. 인천 branch: 구로 → down → 구일 → … → 인천
      const incheonPts: PP[] = [
      tp(guro),
      {
        x: MIN_X,
        y: Y4
      },
      ...positions.slice(45, 65).map(tp)];

      path += ' ' + seg(incheonPts);
      // 4. 광명 spur: 금천구청 → 광명
      const gc = positions.find((p: StationPos) => p.globalIndex === 67);
      const gm = positions.find((p: StationPos) => p.globalIndex === 68);
      if (gc && gm) path += ` M ${gc.x},${gc.y} L ${gm.x},${gm.y}`;
      // 5. 서동탄 spur: 병점 → 서동탄
      const bp = positions.find((p: StationPos) => p.globalIndex === 81);
      const sd = positions.find((p: StationPos) => p.globalIndex === 82);
      if (bp && sd) path += ` M ${bp.x},${bp.y} L ${sd.x},${sd.y}`;
    }
    return path;
  };
  const pathData = buildPath();
  const guroPos = positions[44];
  const gcPos = positions.find((p: StationPos) => p.globalIndex === 67);
  const bpPos = positions.find((p: StationPos) => p.globalIndex === 81);
  const sdPos = positions.find((p: StationPos) => p.globalIndex === 82);
  const gmPos = positions.find((p: StationPos) => p.globalIndex === 68);
  return (
    <div ref={scrollRef} className="w-full overflow-x-auto hide-scrollbar px-2">
      <div
        className="relative mx-auto"
        style={{
          width: '100%',
          minWidth: '1200px',
          maxWidth: '1700px'
        }}>
        
        <svg
          viewBox={`0 0 ${totalWidth} ${totalHeight}`}
          className="w-full h-auto block"
          preserveAspectRatio="xMidYMid meet"
          style={{
            minHeight: `${totalHeight * 0.62}px`
          }}
          onClick={() => onDeselect?.()}>
          
          <rect
            x="0"
            y="0"
            width={totalWidth}
            height={totalHeight}
            fill="transparent" />
          

          {/* ── Route line ── */}
          <path
            d={pathData}
            fill="none"
            stroke="#263C96"
            strokeWidth="7"
            strokeOpacity="0.88"
            strokeLinecap="round"
            strokeLinejoin="round" />
          

          {/* ── Branch direction labels near 구로 ── */}
          {guroPos &&
          <>
              <text
              x={guroPos.x + 16}
              y={guroPos.y - 10}
              fill="#263C96"
              fontSize="9.5"
              fontWeight="700"
              opacity="0.42"
              letterSpacing="-0.3">
              
                ↑ 서울 방면
              </text>
              <text
              x={guroPos.x + 16}
              y={guroPos.y + 18}
              fill="#263C96"
              fontSize="9.5"
              fontWeight="700"
              opacity="0.42"
              letterSpacing="-0.3">
              
                → 천안·신창 방면
              </text>
              <text
              x={guroPos.x + 16}
              y={guroPos.y + 34}
              fill="#263C96"
              fontSize="9.5"
              fontWeight="700"
              opacity="0.42"
              letterSpacing="-0.3">
              
                ↓ 인천 방면
              </text>
            </>
          }

          {/* ── 광명 spur label ── */}
          {gcPos && gmPos &&
          <text
            x={gcPos.x + 6}
            y={(gcPos.y + gmPos.y) / 2 + 4}
            fill="#263C96"
            fontSize="8.5"
            fontWeight="600"
            opacity="0.38"
            letterSpacing="-0.2">
            
              광명 지선
            </text>
          }

          {/* ── 서동탄 spur label ── */}
          {bpPos && sdPos &&
          <text
            x={sdPos.x - 52}
            y={(bpPos.y + sdPos.y) / 2 + 4}
            fill="#263C96"
            fontSize="8.5"
            fontWeight="600"
            opacity="0.38"
            letterSpacing="-0.2">
            
              서동탄 지선
            </text>
          }

          {/* ── Row / branch end labels ── */}
          {/* 소요산 terminal marker */}
          {positions[0] &&
          <text
            x={positions[0].x - 6}
            y={positions[0].y + 3}
            fill="#263C96"
            fontSize="8"
            fontWeight="600"
            opacity="0.3"
            textAnchor="end">
            
              ●
            </text>
          }

          {/* ── Station nodes ── */}
          {positions.map((pos: StationPos) => {
            const isSel = selectedStation?.id === pos.station.id;
            const isXfer = pos.station.hasTransfer;
            const isJunction = JUNCTION_IDS.has(pos.station.id);
            const baseR = isJunction ? 10 : 7;
            const selR = isJunction ? 12 : 10;

            // Curve alignment check for Nokcheon(117/17), Wolgye(118/18), Singil(138/38), Sema(180/80)
            let nodeX = pos.x;
            let nodeY = pos.y;
            const K = 5.5; // Offset to stay on 45deg curve midpoint (0.25 * R)

            if (pos.station.id === '1001000117') { nodeX -= K; nodeY += K; } // 녹천
            if (pos.station.id === '1001000118') { nodeX -= K; nodeY -= K; } // 월계
            if (pos.station.id === '1001000138') { nodeX += K; nodeY += K; } // 신길
            if (pos.station.id === '1001080158') { nodeX -= K; nodeY -= K; } // 세마 (158)

            return (
              <g
                key={pos.station.id}
                data-station-id={pos.station.id}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectStation(pos.station);
                }}>
                
                {/* Selection ring */}
                {isSel &&
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={selR + 7}
                  fill="none"
                  stroke="#263C96"
                  strokeWidth="2"
                  opacity="0.22" />

                }
                {/* Junction emphasis ring */}
                {isJunction && !isSel &&
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={baseR + 5}
                  fill="none"
                  stroke="#263C96"
                  strokeWidth="1.5"
                  opacity="0.14" />

                }
                {/* Transfer outer ring */}
                {isXfer && !isJunction && !isSel &&
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={11}
                  fill="none"
                  stroke="#6B7280"
                  strokeWidth="1.5"
                  opacity="0.45" />

                }
                {/* Main node */}
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={isSel ? selR : baseR}
                  fill={
                  isSel ?
                  '#ffffff' :
                  isJunction ?
                  '#ffffff' :
                  isXfer ?
                  '#ffffff' :
                  '#263C96'
                  }
                  stroke={
                  isSel ?
                  '#263C96' :
                  isJunction ?
                  '#263C96' :
                  isXfer ?
                  '#6B7280' :
                  '#ffffff'
                  }
                  strokeWidth={isSel ? 4 : isJunction ? 3.5 : 3}
                  className="transition-all duration-200" />
                
                {/* Skipping / Non-stop Highlight */}
                {skippingStationIds.includes(pos.station.id) &&
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={baseR + 8}
                  fill="none"
                  stroke="#F43F5E"
                  strokeWidth="3"
                  className="animate-pulse"
                  opacity="0.8" />
                }

                {/* Junction inner dot */}
                {isJunction && !isSel &&
                <circle
                  cx={nodeX}
                  cy={nodeY}
                  r={3}
                  fill="#263C96"
                  opacity="0.55" />

                }
              </g>);
          })}
        </svg>

        {/* ── HTML label overlay ── */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            aspectRatio: `${totalWidth} / ${totalHeight}`
          }}>
          
          {positions.map((pos: StationPos) => {
            const isSel = selectedStation?.id === pos.station.id;
            
            // Re-calculate node position for labels to align with adjusted nodes
            let nodeX = pos.x;
            let nodeY = pos.y;
            const K = 5.5;
            if (pos.station.id === '1001000117') { nodeX -= K; nodeY += K; }
            if (pos.station.id === '1001000118') { nodeX -= K; nodeY -= K; }
            if (pos.station.id === '1001000138') { nodeX += K; nodeY += K; }
            if (pos.station.id === '1001080158') { nodeX -= K; nodeY -= K; }

            const xPct = nodeX / totalWidth * 100;
            const yPct = nodeY / totalHeight * 100;
            return (
              <div
                key={`lbl-${pos.station.id}`}
                className="absolute pointer-events-auto cursor-pointer"
                style={{
                  left: `${xPct}%`,
                  top: `${yPct}%`
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectStation(pos.station);
                }}>
                
                <StationLabel
                  station={pos.station}
                  isSelected={isSel}
                  isSkipping={skippingStationIds.includes(pos.station.id)}
                  position={pos.labelPos}
                  isJunction={JUNCTION_IDS.has(pos.station.id)} />
                
              </div>);

          })}
        </div>
      </div>
    </div>);

};
// ── Station label ─────────────────────────────────────────────────────────────
function StationLabel({
  station,
  isSelected,
  isSkipping,
  position,
  isJunction
}: {station: Station;isSelected: boolean;isSkipping: boolean;position: 'top' | 'bottom' | 'left' | 'right';isJunction: boolean;}) {
  // Enhanced offsets for specific stations to improve legibility (Guro, Singil, Wolgye, Nokcheon, Geumcheon-gu Office, Byeongjeom)
  const isCrowded = ['117', '118', '138', '141', '164', '178'].includes(station.id);
  const extraOffset = isCrowded ? 10 : 0;

  const OH = (isJunction ? 24 : 20) + extraOffset; // offset for top/bottom
  const OV = (isJunction ? 26 : 22) + extraOffset; // offset for left/right
  const posStyle: React.CSSProperties = (() => {
    switch (position) {
      case 'top':
        return {
          bottom: `${OH}px`,
          left: '50%',
          transform: 'translateX(-50%)'
        };
      case 'bottom':
        return {
          top: `${OH}px`,
          left: '50%',
          transform: 'translateX(-50%)'
        };
      case 'left':
        return {
          right: `${OV}px`,
          top: '50%',
          transform: 'translateY(-50%)'
        };
      case 'right':
        return {
          left: `${OV}px`,
          top: '50%',
          transform: 'translateY(-50%)'
        };
    }
  })();
  const align =
  position === 'left' ?
  'text-right' :
  position === 'right' ?
  'text-left' :
  'text-center';
  return (
    <div className={`absolute select-none ${align} group`} style={posStyle}>
      <span
        className={`station-label block font-bold leading-tight transition-colors
          ${isJunction ? 'text-[12px]' : 'text-[11px]'}
          ${isSelected ? 'text-line1' : isJunction ? 'text-gray-800 group-hover:text-line1' : 'text-gray-700 group-hover:text-line1'}`}
        style={{
          whiteSpace: 'nowrap',
          letterSpacing: '-0.02em'
        }}>
        
        {station.name}
      </span>
      {isSkipping &&
      <span className="block text-[8px] font-extrabold text-rose-500 animate-bounce leading-none mt-0.5">
        무정차 통과
      </span>
      }
      {station.hasTransfer &&
      <div
        className={`flex flex-wrap gap-0.5 mt-0.5
            ${position === 'left' ? 'justify-end' : position === 'right' ? 'justify-start' : 'justify-center'}`}>
        
          {station.transferLines.slice(0, 2).map((line) =>
        <span
          key={line}
          className="text-[8.5px] text-gray-600 bg-gray-200 px-1 rounded-sm leading-none inline-block py-0.5 border border-gray-300"
          style={{
            whiteSpace: 'nowrap',
            fontWeight: '600'
          }}
          title={line}>
          
              {line}
            </span>
        )}
        </div>
      }
    </div>);

}