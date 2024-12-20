from datetime import datetime, timedelta
import pulp
import pandas as pd


class Emma_generator:
    
    def __init__(self,base,setting,AOR):
        # 一般設定
        self.company_limit = int(setting[1][1])#1週間のうちの労働数
        i = 5
        dep_name = set([d[7] for d in setting[5:]])
        Employee_prof = {}
        Department_prof = {}
        for n in dep_name:
             Employee_prof[n] = {}
             Department_prof[n] = []
        while len(setting)>i and setting[i][1]!='':
             Employee_prof[setting[i][1]][setting[i][0]] = [d for dx,d in enumerate(setting[i]) if dx in [2,3,4,5]]
             Employee_prof[setting[i][1]][setting[i][0]][0] = int(Employee_prof[setting[i][1]][setting[i][0]][0] )
             i += 1
             
        self.Employee_prof = Employee_prof
        '''
        {'casher':{'Alice':[40,'lunch','dinner'],
                'Bob':[40,'lunch'],
                'Cindy':[20,'lunch']
                },
                'shopper':{'Dauntless':[40,'morning']
                }}
        '''
        i = 5
        while len(setting)>i and setting[i][7]!="":
            data = [setting[i][8]]
            data.append(setting[i][9].replace(',',' '))

            
            data = data + [int(d) for dx,d in enumerate(setting[i]) if dx in [10,11,12,13,14] ]
            data[1] = data[1].replace(',',' ')
            Department_prof[setting[i][7]].append(data)
            i += 1
        self.Department_prof = Department_prof
        '''
        self.Department_prof = {'casher':[['lunch','Alice Bob',8,0,1,1,2],
                ['dinner','Bob',8,0,1,1,1]],
                'shopper':[['morning','',8,0,1,1,1]]
                }
        '''
        
        Holiday = []
        for i, row in enumerate(base[4:]):
            for j, value in enumerate(row[1:]):
                if '休' in value:
                    Holiday.append([base[i][0],base[0][j]])
        self.Holiday = Holiday
        '''
            [['Alice','2024/9/22'],
            ['Alice','2024/9/23'],
            ['Cindy','2024/9/24']]
        '''
        AOR = []
        self.AOR = AOR
    def make_day_list(self,start_day,end_day):
            dt_start = datetime.strptime(start_day, "%Y/%m/%d")
            dt_end = datetime.strptime(end_day, "%Y/%m/%d")
            bizz_dates = []
            current_date = dt_start
            while current_date <= dt_end:
                bizz_dates.append(current_date)
                current_date += timedelta(days=1)
            return bizz_dates
    def limit_cut(self,depart):
            company_limit = self.company_limit
            for emp in enumerate(self.Employee_prof[depart].keys()):
                if self.Employee_prof[depart][emp[1]][0]<company_limit-10:
                    self.Employee_prof[depart][emp[1]][0]=self.Employee_prof[depart][emp[1]][0]+10
                else:
                    self.Employee_prof[depart][emp[1]][0]=self.Employee_prof[depart][emp[1]][0]+1
    def AOR_cut(self,AOR):
            for i,a in enumerate(AOR):
                if a>0:
                    AOR[i] = AOR[i]-1
            return AOR
    def shift_generator(self,start_day,end_day,depart_name,N):
            AOR = self.AOR
            company_limit = self.company_limit
            Department_prof = self.Department_prof   
            day_list = self.make_day_list(start_day,end_day)
            Employee_prof = self.Employee_prof
            print(f'--------------------begin {depart_name}--------------------')
            shifts = Department_prof[depart_name]
            Employee_dict = Employee_prof[depart_name]
            Employees = Employee_dict.keys()
            # 線形計画を定義
            prob = pulp.LpProblem("Shift", pulp.LpMinimize)
            x = {}
            for d in day_list:
                for s in shifts:
                    s = s[0]
                    for e in Employees:
                        if(s in Employee_dict[e]):
                            x[d,s,e] = pulp.LpVariable(f"x({d},{s},{e})", cat="Binary")
            '''
            希望休
            '''
            Holiday = [[d[0],datetime.strptime(d[1], '%Y/%m/%d')] for d in self.Holiday]
            for h in Holiday:
                e = h[0]
                d = h[1]
                for s in shifts:
                    if s[0] in Employee_dict[e]:
                        prob += x[d, s[0], e] == 0
            '''
            夜勤配慮
            '''
            for e in Employees:
                for s in shifts:
                    if(s[3]==1 and s in Employee_dict[e]):
                        for d in day_list[1:]:
                            prob += pulp.lpSum([x[d,s1[0],e] -x[d-timedelta(days=1), s[0], e] for s1 in shifts if s1!=s and s1[3]!=1 and s1[0] in Employee_dict[e]]) < 1
                    
            '''
            weekly limit ,シフトは一つまで
            '''
            for e in Employees:
                limit = min(company_limit,Employee_dict[e][0])
                for d in day_list[7:]:
                    prob += pulp.lpSum([x[d-timedelta(days=i), s[0], e]*s[2] for i in range(7) for s in shifts if s[0] in Employee_dict[e]]) <= limit
                    prob += pulp.lpSum([x[d, s[0], e] for s in shifts if s[0] in Employee_dict[e]]) <=1
            '''
            必要人数,リーダー
            '''
            for s in shifts:
                for k,d in enumerate(day_list):
                    prob += pulp.lpSum([x[d, s[0], e] for e in Employees if s[0] in Employee_dict[e]])>=s[4+AOR[k]]
                    prob += pulp.lpSum([x[d, s[0], e] for e in Employees if s[0] in Employee_dict[e] and e in s[1].split()])>=1
            '''
            勤務日数平滑化
            '''
    
            for e in Employees:
                prob += pulp.lpSum([x[d, s[0], e] for s in shifts for d in day_list if s[0] in Employee_dict[e]])-pulp.lpSum([x[d, s[0], e1] for e1 in Employees for s in shifts for d in day_list if s[0] in Employee_dict[e1]])/len(Employees)>=-4*N
               
            '''
            目的関数
            '''
            prob += pulp.lpSum(x[d, s[0],e] for e in Employees for s in shifts for d in day_list if s[0] in Employee_dict[e])

            # 計算
            solver = pulp.COIN_CMD(path='/usr/local/bin/cbc',msg=True,gapRel=0.015, timeLimit=120)
            status = prob.solve(solver)
            
            data = []
            for e in Employees:
                row = []
                for d in day_list:
                    judge = 0
                    for s in shifts :
                        if s[0] in Employee_dict[e] and x[d,s[0],e].varValue==1 and judge==0:
                            row.append(s[0])
                            judge=1
                    if judge==0:
                        row.append('休み')
                data.append(row)
            df = pd.DataFrame(data, index=[f"{e}" for e in Employees], columns=[str(d) for d in day_list])
            return pulp.LpStatus[status],df

    def fit(self,start_day,end_day):
            departments = self.Department_prof.keys()
            AOR_base = self.AOR
            day_list = self.make_day_list(start_day,end_day)
            df_shift = pd.DataFrame()
            df_shift.set_index(0, inplace=True)
            df_shift.columns = [str(d) for d in day_list]
            for depart_name in departments:
                df_shift = pd.concat([df_shift,pd.DataFrame([[]],index=[f'{depart_name}'])],axis=0)
                status = 'Infeasible'
                l = 0
                i = 0
                j = 0
                N = 0
                while l<2 and status == 'Infeasible':#休日カット
                    i = 0
                    while i<3 and status == 'Infeasible':#limitカット
                        self.AOR = AOR_base
                        j = 0
                        while j<3 and status == 'Infeasible':#AORカット
                            N = 0
                            while N<5 and status == 'Infeasible':#N増大
                                status,df = self.shift_generator(start_day,end_day,depart_name,N)
                                N+=1
                            self.AOR = self.AOR_cut(self.AOR)

                            j+=1
                        self.limit_cut(depart_name)
                        i+=1
                    self.Holiday = []
                    l += 1
                df_shift = pd.concat([df_shift,df],axis=0)
                i2 = i
                l2 = l
                N2 = N
                j2 = j
            report  = f'{start_day}からのシフト案を生成しました。'
            if l2>1 or i2>1:
                report = report+' 希望休や労働上限を無視している可能性があります。'
            if N2>1 or j2>1:
                report = report +' 必要人数が足りているか、労働日数が公平か確認してください。'
            if report == f'{start_day}からのシフト案を生成しました。':
                report = report + ' ご確認下さい🙇'
            df_shift = pd.concat([df_shift,pd.DataFrame([[]],index = [report])],axis=0)
            df_shift.columns = [df_shift.columns[0]] + [datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y/%m/%d') for date_str in df_shift.columns[1:]]

            return df_shift.fillna('').reset_index()
 
