// SPDX-License-Identifier: GPL-3.0-or-later
// Windows translation of PSXS5's pinned tooling/radv/radv-link.sh.
// All ABI bindings are read from that source; no unsupported imports hidden.
const fs = require('fs'), path = require('path'), cp = require('child_process');
const root = __dirname, p = s => path.join(root, s);
const sdk = p('deps/ps5-payload-sdk');
const rsdk = p('deps/radv-sdk/ps5-payload-sdk');
const upstream = p('upstream/PSXS5-5c17ea31aec5791c12451e915386fa98d670adb4');
const llvm = p('deps/llvm/bin');
const out = p('build-vulkan');
fs.mkdirSync(p('build-vulkan/obj'), {recursive:true});
const log = fs.openSync(p('BUILD-VULKAN.txt'), 'w');
function run(name, args) {
    fs.writeSync(log, JSON.stringify({name,args}) + '\n');
    const r = cp.spawnSync(path.join(llvm, name+'.exe'), args, {cwd:root, windowsHide:true, stdio:['ignore',log,log]});
    if(r.status !== 0) throw Error(name+' failed; see BUILD-VULKAN.txt');
}
const common = ['-target','x86_64-sie-ps5','--sysroot='+sdk+'/target','-isystem',sdk+'/target/include',
    '-O2','-g','-fPIC','-fno-stack-protector','-fno-plt','-femulated-tls','-ffunction-sections','-fdata-sections'];
const objects = [];
function compile(source, name, flags=[]) {
    const obj=p('build-vulkan/obj/'+name+'.o');
    run('clang',[...common,...flags,'-c',source,'-o',obj]); objects.push(obj);
}
compile(p('native-vulkan/main.c'),'main',['-std=c11','-I'+p('sdl3-src/include')]);
compile(p('native-vulkan/unsupported.c'),'unsupported',['-std=c11']);
// Same native CRT as the GPU clear; source and original object retained.
objects.push(p('build-clear/obj/app_crt.o'));
compile(path.join(upstream,'tooling/native/app_cpp_runtime.cpp'),'cpp_runtime',
    ['-std=c++20','-fno-exceptions','-fno-rtti','-I'+rsdk+'/target/include/c++/v1']);
for (const name of ['emutls','udivmodti4','udivti3','divti3','modti3','umodti3','x86'])
    compile(p('deps/compiler-rt/'+name+'.c'),name,['-std=c11']);
const recipe = fs.readFileSync(path.join(upstream,'tooling/radv/radv-link.sh'),'utf8');
const bindings = new Set();
for (const match of recipe.matchAll(/for name in ([\s\S]*?); do([\s\S]*?)\n    done/g)) {
    if(match[2].includes('--defsym=')) for (const name of match[1].replace(/\\\r?\n/g,' ').trim().split(/\s+/))
        bindings.add(name);
}
const platformSymbols = fs.readFileSync(p('PLATFORM-SYMBOLS.txt'),'utf8');
if (/ T ps5_localeconv\r?\n/.test(platformSymbols)) bindings.add('localeconv');
const optionalBindings = new Set(['strcasestr','mkstemp','readlink','link','symlink']);
for (const name of [...bindings]) if (!new RegExp(' T ps5_'+name+'(?:\\r?\\n|$)').test(platformSymbols)) {
    if (optionalBindings.has(name)) bindings.delete(name);
    else throw Error('Pinned platform lacks binding ps5_'+name);
}
const wraps = ['pthread_create','pthread_join','pthread_detach','fclose','fflush',
    'malloc','calloc','realloc','free','posix_memalign','aligned_alloc','memalign','malloc_usable_size','reallocf','reallocarray','getline','getdelim'];
const support=p('upstream/PSXS5-5c17ea31aec5791c12451e915386fa98d670adb4/tooling/native');
const args=['-m','elf_x86_64','-pie','--no-dynamic-linker',
    '-z','max-page-size=0x4000','--eh-frame-hdr','--gc-sections','--exclude-libs=ALL','--error-limit=0',
    '-L'+support,'-T',path.join(upstream,'tooling/psbc/ps5-pie-unwind.ld'),
    '--version-script='+path.join(support,'app-symbols.map'),'-e','_start',
    '--defsym=readlink=cpe_readlink','--defsym=mkstemp=cpe_mkstemp',
    ...wraps.map(n=>'--wrap='+n),...[...bindings].map(n=>'--defsym='+n+'=ps5_'+n),
    ...objects,p('build-sdl/libSDL3.a'),'--whole-archive',p('deps/radv-release/lib/libvulkan_radeon.ps5.a'),
    '--no-whole-archive','--start-group',rsdk+'/target/lib/libc++.a',rsdk+'/target/lib/libc++abi.a',
    rsdk+'/target/lib/libunwind.a',rsdk+'/target/lib/libps5platform.a','--end-group',
    '-L'+sdk+'/target/lib','--as-needed',...fs.readdirSync(sdk+'/target/lib').filter(n=>n.endsWith('.so')&&!n.includes('kernel_sys')&&!n.includes('kernel_web')).map(n=>sdk+'/target/lib/'+n),
    '-o',p('build-vulkan/gpu-vulkan.elf')];
fs.writeFileSync(p('build-vulkan/LINK-ARGS.json'),JSON.stringify(args,null,2));
run('ld.lld',args);
for(const [tool,args,file] of [['llvm-nm',['-n',p('build-vulkan/gpu-vulkan.elf')],'SYMBOLS.txt'],
    ['llvm-readelf',['--dynamic','--dyn-syms','--program-headers',p('build-vulkan/gpu-vulkan.elf')],'IMPORTS-SEGMENTS.txt']]) {
    const r=cp.spawnSync(path.join(llvm,tool+'.exe'),args,{encoding:'utf8',windowsHide:true});
    if(r.status) throw Error(tool+' failed'); fs.writeFileSync(path.join(out,file),r.stdout);
}
fs.closeSync(log);
console.log('Native static RADV / SDL_GPU application linked. No hardware run.');
