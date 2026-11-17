"""Paper notes and a fictional stationary computer; no host or internet actions."""
import copy
import uuid

STUDY_KINDS={'write_note','read_notes','power_on','power_off','computer_work'}
STUDY_LABELS={'write_note':'写笔记','read_notes':'翻阅笔记','power_on':'打开电脑','power_off':'关闭电脑','computer_work':'使用电脑'}
MODES={'writing':'写作','organize':'整理文档','gaming':'玩游戏'}


def defaults(kind):
    if kind=='book':return {'pages':120,'page':0}
    if kind=='water':return {'servings':3,'capacity':3}
    if kind=='notebook':return {'notes':[],'last_read_at':None}
    if kind=='computer':return {'powered':False,'documents':[],'gaming_minutes':0,'organize_count':0,'completed_sessions':0}
    return {}


def content(step,limit):
    title=step.get('title','未命名记录');text=step.get('text','')
    if not isinstance(title,str) or not 1<=len(title.strip())<=60:raise ValueError('记录标题需为 1–60 字')
    if not isinstance(text,str) or not 1<=len(text.strip())<=limit:raise ValueError(f'请提供 1–{limit} 字的记录内容')
    return title.strip(),text.strip()


def check(state,item,step,actor,now):
    kind=step['kind']
    if not item:raise ValueError('物品不存在')
    if item.get('retired'):raise ValueError('物品已停用，已保存记录仅供查阅')
    if kind in {'write_note','read_notes'}:
        if item['kind']!='notebook' or not item['carried']:raise ValueError('需要先拿到纸质笔记本')
        if item.get('wet_until',0)>now:raise ValueError('笔记本潮湿，需要先晾干')
        if kind=='read_notes':
            if not item.get('notes'):raise ValueError('笔记本还没有记录可读')
            return 60
        content(step,500)
        if len(item.get('notes',[]))>=50:raise ValueError('笔记本记录已满，请使用另一本')
        return 300
    if item['kind']!='computer':raise ValueError('这不是电脑')
    if item.get('carried') or item.get('place_id')!=actor['place_id'] or item.get('room_id')!=state.get('room_id'):raise ValueError('需要在电脑所在房间使用，电脑不是随身物品')
    if kind=='power_on':
        if item.get('powered'):raise ValueError('电脑已经开机')
        return 10
    if not item.get('powered'):raise ValueError('需要先打开电脑')
    if kind=='power_off':return 10
    mode=step.get('mode','writing')
    if mode not in MODES:raise ValueError('电脑任务支持写作、整理文档或游戏')
    if mode=='writing':
        content(step,1000)
        if len(item.get('documents',[]))>=50:raise ValueError('电脑草稿已达 50 篇，暂不新增')
    elif mode=='organize' and not item.get('documents'):raise ValueError('电脑中还没有可整理的文档')
    return 300 if mode=='organize' else 600


def apply(item,step,now):
    kind=step['kind']
    if kind=='power_on':item['powered']=True
    elif kind=='power_off':item['powered']=False
    elif kind=='read_notes':item['last_read_at']=now
    elif kind=='write_note':
        title,text=content(step,500)
        item.setdefault('notes',[]).append({'id':'note_'+uuid.uuid4().hex,'title':title,'text':text,'created_at':now,'fact_kind':'fiction'})
    elif kind=='computer_work':
        mode=step.get('mode','writing')
        item['completed_sessions']=item.get('completed_sessions',0)+1
        if mode=='writing':
            title,text=content(step,1000)
            item.setdefault('documents',[]).append({'id':'draft_'+uuid.uuid4().hex,'title':title,'text':text,'created_at':now,'fact_kind':'fiction'})
        elif mode=='gaming':item['gaming_minutes']=item.get('gaming_minutes',0)+10
        elif mode=='organize':item['organize_count']=item.get('organize_count',0)+1
        item['last_mode']=mode
    item['last_used_at']=now


def present(item,admin=False):
    value=copy.deepcopy(item)
    for key,label in [('notes','note_count'),('documents','document_count')]:
        if key in value:
            value[label]=len(value[key])
            if not admin:value[key]=value[key][-2:]
    return value


def receipt(item,step):
    result=present(item)
    if item['kind'] in {'notebook','computer'}:
        # A receipt stores the effect of this step, not the whole previous book.
        for key in ('notes','documents'):
            values=result.pop(key,[])
            if values and (step['kind']=='write_note' or step['kind']=='computer_work' and step.get('mode','writing')=='writing'):result['saved_record']=values[-1]
    return result
