import {Audio} from '@remotion/media';
import {AbsoluteFill,Easing,Img,interpolate,staticFile,useCurrentFrame} from 'remotion';

type Joint={x:number;y:number;score:number};
type Person={id:string;usable:boolean;joints:Record<string,Joint>};
export type PoseData={sourceImage:string;threshold:number;people:Person[]};

const links:[string,string][]=[['left_shoulder','right_shoulder'],['left_shoulder','left_elbow'],['left_elbow','left_wrist'],['right_shoulder','right_elbow'],['right_elbow','right_wrist'],['left_shoulder','left_hip'],['right_shoulder','right_hip'],['left_hip','right_hip'],['left_hip','left_knee'],['left_knee','left_ankle'],['right_hip','right_knee'],['right_knee','right_ankle']];
const palette=['#d64b22','#2474d8','#4d9820'];
const px=(joint:Joint,axis:'x'|'y')=>joint[axis]*(axis==='x'?576:720);
const visible=(joint:Joint|undefined,threshold:number)=>Boolean(joint&&joint.score>=threshold);

const Figure=({person,index,threshold}:{person:Person;index:number;threshold:number})=>{const color=palette[index%palette.length],j=person.joints,nose=j.nose,ls=j.left_shoulder,rs=j.right_shoulder;const headRadius=visible(ls,threshold)&&visible(rs,threshold)?Math.max(22,Math.hypot(px(ls,'x')-px(rs,'x'),px(ls,'y')-px(rs,'y'))*.27):28;return <g>
  {links.map(([a,b])=>visible(j[a],threshold)&&visible(j[b],threshold)?<line key={`${a}-${b}`} x1={px(j[a],'x')} y1={px(j[a],'y')} x2={px(j[b],'x')} y2={px(j[b],'y')} stroke={color} strokeWidth="10" strokeLinecap="round"/>:null)}
  {visible(nose,threshold)&&<><circle cx={px(nose,'x')} cy={px(nose,'y')} r={headRadius} fill="#fff8df" stroke={color} strokeWidth="7"/><path d={`M${px(nose,'x')-headRadius*.95} ${px(nose,'y')-headRadius*.45} Q${px(nose,'x')} ${px(nose,'y')-headRadius*1.15} ${px(nose,'x')+headRadius*.95} ${px(nose,'y')-headRadius*.45}`} fill="#92703a" stroke="#171717" strokeWidth="5"/><circle cx={px(nose,'x')-headRadius*.25} cy={px(nose,'y')-3} r="3.5" fill="#111"/><circle cx={px(nose,'x')+headRadius*.25} cy={px(nose,'y')-3} r="3.5" fill="#111"/></>}
  {[...new Set(links.flat())].map(name=>visible(j[name],threshold)?<circle key={name} cx={px(j[name],'x')} cy={px(j[name],'y')} r="6" fill="#fff" stroke={color} strokeWidth="4"/>:null)}
  {index===0&&visible(j.left_shoulder,threshold)&&<path d={`M${px(j.left_shoulder,'x')-22} ${px(j.left_shoulder,'y')+12} L${px(j.left_hip,'x')+30} ${px(j.left_hip,'y')+145}`} stroke="#67472e" strokeWidth="9"/>}
  {index===2&&visible(j.right_shoulder,threshold)&&<path d={`M${px(j.right_shoulder,'x')+12} ${px(j.right_shoulder,'y')-35} L${px(j.right_hip,'x')+30} ${px(j.right_hip,'y')+155}`} stroke="#67472e" strokeWidth="9"/>}
  <text x={visible(nose,threshold)?px(nose,'x'):0} y={visible(nose,threshold)?px(nose,'y')+headRadius+28:0} textAnchor="middle" fontFamily="Arial" fontWeight="900" fontSize="15" fill="#111">{index===1?'FIELD LEADER':'GUERRILLA'}</text>
  </g>};

export const PhotoPoseScene=({poseData}:{poseData:PoseData})=>{const frame=useCurrentFrame(),phase=frame<55?0:frame<100?1:2,phaseStart=phase===0?0:phase===1?55:100,fade=interpolate(frame-phaseStart,[0,8],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.out(Easing.cubic)}),people=poseData.people.filter(p=>p.usable).slice(0,3);return <AbsoluteFill style={{background:'#fff',fontFamily:'Arial,sans-serif',overflow:'hidden'}}>
  <Audio src={staticFile('wiki-tests/ramon-magsaysay/audio/rm-02.wav')}/>
  <div style={{position:'absolute',left:45,top:28,fontSize:18,fontWeight:900,letterSpacing:4,color:'#bd321f'}}>LUZON · 1942</div><div style={{position:'absolute',left:45,top:58,fontSize:39,fontWeight:950,letterSpacing:-1}}>FROM PHOTOGRAPH TO RECONSTRUCTION</div>
  <div style={{position:'absolute',left:92,top:125,width:460,height:576,opacity:fade,boxShadow:'0 10px 30px #0003',overflow:'hidden',background:'#eee'}}>
    {phase<2&&<Img src={staticFile(phase===0?'wiki-tests/ramon-magsaysay/media/wartime-guerrillas.jpg':'wiki-tests/ramon-magsaysay/pose-tests/wartime-guerrillas/pose-overlay.jpg')} style={{width:'100%',height:'100%',objectFit:'fill'}}/>}
    {phase===2&&<svg viewBox="0 0 576 720" width="100%" height="100%" style={{background:'#fff'}}>{people.map((person,i)=><Figure key={person.id} person={person} index={i} threshold={poseData.threshold}/>)}</svg>}
  </div>
  <div style={{position:'absolute',left:620,top:172,right:52}}><div style={{fontSize:21,fontWeight:900,letterSpacing:3,color:phase===0?'#bd321f':'#999'}}>01 · ARCHIVAL SOURCE</div><div style={{marginTop:46,fontSize:21,fontWeight:900,letterSpacing:3,color:phase===1?'#bd321f':'#999'}}>02 · LOCAL POSE EXTRACTION</div><div style={{marginTop:46,fontSize:21,fontWeight:900,letterSpacing:3,color:phase===2?'#bd321f':'#999'}}>03 · REUSABLE SCENE</div><div style={{marginTop:78,fontSize:30,fontWeight:900,lineHeight:1.18}}>The photograph supplies the blocking. The engine redraws the people.</div><div style={{marginTop:30,fontSize:17,lineHeight:1.45,color:'#555'}}>Three foreground bodies retained.<br/>Three background detections rejected.</div></div>
  <div style={{position:'absolute',right:40,bottom:24,fontSize:11,color:'#666'}}>WIKIMEDIA COMMONS · PUBLIC DOMAIN</div>
  </AbsoluteFill>};
